#include "crash.h"
#include "sdl_wrappers.h"

#if defined(BACKTRACE)

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <initializer_list>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <typeinfo>

#if defined(_WIN32)
#if 1 // HACK: Hack to prevent reordering of #include "platform_win.h" by IWYU
#include "platform_win.h"
#endif
#include <dbghelp.h>
#endif

#if defined(__APPLE__) && defined(TILES) && !defined(__ANDROID__)
#include <CoreFoundation/CoreFoundation.h>
#endif

#include "debug.h"
#include "get_version.h"
#include "path_info.h"

// signal handlers are expected to have C linkage, and only use the
// common subset of C & C++

// Ensures only the first crash path (exception filter or signal handler) logs and dumps.
namespace
{

auto g_crash_logged = std::atomic_flag {};
auto g_crash_report_durable = std::atomic_bool { false };
auto g_crash_handling_complete = std::atomic_bool { false };
auto g_main_thread_id = std::thread::id {};
auto g_main_thread_id_set = std::atomic_flag {};
constexpr auto crash_handler_timeout = std::chrono::seconds { 30 };
constexpr auto crash_handler_wait_step = std::chrono::milliseconds { 10 };

auto reset_signal_to_default( int sig ) -> void
{
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunknown-pragmas"
#pragma GCC diagnostic ignored "-Wold-style-cast"
#pragma GCC diagnostic ignored "-Wzero-as-null-pointer-constant"
    std::signal( sig, SIG_DFL );
#pragma GCC diagnostic pop
}

auto wait_for_crash_handling_completion() -> void
{
    while( !g_crash_handling_complete.load( std::memory_order_acquire ) ) {
        std::this_thread::sleep_for( crash_handler_wait_step );
    }
}

auto write_crash_log_file( const std::string &crash_log_file,
                           const std::string &log_text ) -> void
{
    auto *file = fopen( crash_log_file.c_str(), "w" );
    if( file ) {
        fwrite( log_text.data(), 1, log_text.size(), file );
        fclose( file );
    }
}

auto start_crash_handling_watchdog() -> void
{
    try {
        auto watchdog = std::thread( []() {
            std::this_thread::sleep_for( crash_handler_timeout );
            if( !g_crash_report_durable.load( std::memory_order_acquire ) ) {
                std::_Exit( EXIT_FAILURE );
            }
        } );
        watchdog.detach();
    } catch( ... ) {
    }
}

#if defined(TILES) && !defined(__ANDROID__)
auto show_crash_dialog( const std::string &crash_log_file,
                        const std::string &header_text,
                        std::ostringstream &log_text ) -> void
{
#if defined(__APPLE__)
    static_cast<void>( crash_log_file );
    static_cast<void>( log_text );
    auto *message = CFStringCreateWithCString( nullptr, header_text.c_str(),
                    kCFStringEncodingUTF8 );
    auto response = CFOptionFlags{ 0 };
    CFUserNotificationDisplayAlert( 0, kCFUserNotificationStopAlertLevel,
                                    nullptr, nullptr, nullptr,
                                    CFSTR( "Error" ), message, nullptr,
                                    nullptr, nullptr, &response );
    if( message ) {
        CFRelease( message );
    }
#else
    if( std::this_thread::get_id() != g_main_thread_id ) {
        return;
    }
    if( SDL_ShowSimpleMessageBox( SDL_MESSAGEBOX_ERROR, "Error",
                                  header_text.c_str(), nullptr ) != 0 ) {
        log_text << "Error creating SDL message box: " << SDL_GetError() << '\n';
        write_crash_log_file( crash_log_file, log_text.str() );
    }
#endif
}
#endif

}

#if defined(_WIN32)
// Set by windows_exception_filter; used by dump_to() and debug_write_backtrace().
static EXCEPTION_POINTERS *g_exception_info = nullptr;
#endif

extern "C" {

#if defined(_WIN32)
    static void dump_to( const char *file )
    {
        HANDLE handle = CreateFile( file, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                                    FILE_ATTRIBUTE_NORMAL, nullptr );
        MINIDUMP_EXCEPTION_INFORMATION mdei = {};
        MINIDUMP_EXCEPTION_INFORMATION *mdei_ptr = nullptr;
        if( g_exception_info ) {
            mdei.ThreadId          = GetCurrentThreadId();
            mdei.ExceptionPointers = g_exception_info;
            mdei.ClientPointers    = FALSE;
            mdei_ptr               = &mdei;
        }
        MiniDumpWriteDump( GetCurrentProcess(),
                           GetCurrentProcessId(),
                           handle,
                           static_cast<MINIDUMP_TYPE>( MiniDumpNormal | MiniDumpWithUnloadedModules ),
                           mdei_ptr, nullptr, nullptr );
        CloseHandle( handle );
    }
#endif

    static void log_crash( const char *type, const char *msg )
    {
        if( g_crash_logged.test_and_set( std::memory_order_acq_rel ) ) {
            wait_for_crash_handling_completion();
            return;
        }


        const auto crash_log_file = PATH_INFO::crash();
#if defined(_WIN32)
        const auto minidump_file = crash_log_file + ".dmp";
#endif
        auto log_text = std::ostringstream {};
#if defined(__ANDROID__)
        // At this point, Android JVM is already doomed
        // No further UI interaction (including the SDL message box)
        // Show a dialogue at next launch
        log_text << "VERSION: " << getVersionString()
                 << '\n' << type << ' ' << msg;
#else
        log_text << "The program has crashed."
                 << "\nSee the log file for a stack trace."
                 << "\nCRASH LOG FILE: " << crash_log_file
#if defined(_WIN32)
                 << "\nMINIDUMP FILE:  " << minidump_file
                 << "\n(Attach both files when reporting this crash)"
#endif
                 << "\nVERSION: " << getVersionString()
                 << "\nTYPE: " << type
                 << "\nMESSAGE: " << msg;
#endif
        const auto header_text = log_text.str();
        write_crash_log_file( crash_log_file,
                              header_text +
                              "\nSTACK TRACE:\nStack trace collection has not completed.\n" );

        start_crash_handling_watchdog();

        flush_debug_log();

#if defined(_WIN32)
        dump_to( minidump_file.c_str() );
#endif

        log_text << "\nSTACK TRACE:\n";
        debug_write_backtrace( log_text );
        write_crash_log_file( crash_log_file, log_text.str() );
        std::cerr << log_text.str();

        g_crash_report_durable.store( true, std::memory_order_release );

#if defined(TILES) && !defined(__ANDROID__)
        show_crash_dialog( crash_log_file, header_text, log_text );
#endif
#if defined(__ANDROID__)
        // Create a placeholder dummy file "config/crash.log.prompt"
        // to let the app show a dialog box at next start
        auto *file = fopen( ( crash_log_file + ".prompt" ).c_str(), "w" );
        if( file ) {
            fwrite( "0", 1, 1, file );
            fclose( file );
        }
#endif
        g_crash_handling_complete.store( true, std::memory_order_release );
    }

    static void signal_handler( int sig )
    {
        const char *msg;
        switch( sig ) {
            case SIGSEGV:
                msg = "SIGSEGV: Segmentation fault";
                break;
            case SIGILL:
                msg = "SIGILL: Illegal instruction";
                break;
            case SIGABRT:
                msg = "SIGABRT: Abnormal termination";
                break;
#if defined(SIGBUS)
            case SIGBUS:
                msg = "SIGBUS: Bus error";
                break;
#endif
            case SIGFPE:
                msg = "SIGFPE: Arithmetical error";
                break;
#if defined(SIGTRAP)
            case SIGTRAP:
                msg = "SIGTRAP: Trace trap";
                break;
#endif
            default:
                return;
        }
        log_crash( "Signal", msg );
        reset_signal_to_default( sig );
        std::raise( sig );
        std::_Exit( EXIT_FAILURE );
    }
} // extern "C"

#if defined(_WIN32)
static LONG WINAPI windows_exception_filter( EXCEPTION_POINTERS *exception_info )
{
    g_exception_info = exception_info;
    set_crash_exception_context( exception_info ? exception_info->ContextRecord : nullptr );
    const char *msg = "Unknown exception";
    if( exception_info && exception_info->ExceptionRecord ) {
        switch( exception_info->ExceptionRecord->ExceptionCode ) {
            case EXCEPTION_ACCESS_VIOLATION:
                msg = "EXCEPTION_ACCESS_VIOLATION: Access violation";
                break;
            case EXCEPTION_ILLEGAL_INSTRUCTION:
                msg = "EXCEPTION_ILLEGAL_INSTRUCTION: Illegal instruction";
                break;
            case EXCEPTION_STACK_OVERFLOW:
                msg = "EXCEPTION_STACK_OVERFLOW: Stack overflow";
                break;
            case EXCEPTION_INT_DIVIDE_BY_ZERO:
                msg = "EXCEPTION_INT_DIVIDE_BY_ZERO: Integer divide by zero";
                break;
            case EXCEPTION_FLT_DIVIDE_BY_ZERO:
                msg = "EXCEPTION_FLT_DIVIDE_BY_ZERO: Float divide by zero";
                break;
            default:
                break;
        }
    }
    log_crash( "Signal", msg );
    return EXCEPTION_CONTINUE_SEARCH;
}
#endif

[[noreturn]] static void crash_terminate_handler()
{
    const char *type;
    const char *msg;
    try {
        auto &&ex = std::current_exception(); // *NOPAD*
        if( ex ) {
            std::rethrow_exception( ex );
        } else {
            type = msg = "Unexpected termination";
        }
    } catch( const std::exception &e ) {
        type = typeid( e ).name();
        msg = e.what();
        // call here to avoid `msg = e.what()` going out of scope
        log_crash( type, msg );
        reset_signal_to_default( SIGABRT );
        abort();
    } catch( ... ) {
        type = "Unknown exception";
        msg = "Not derived from std::exception";
    }
    log_crash( type, msg );
    reset_signal_to_default( SIGABRT );
    abort();
}

void init_crash_handlers()
{
    if( !g_main_thread_id_set.test_and_set( std::memory_order_acq_rel ) ) {
        g_main_thread_id = std::this_thread::get_id();
    }
#if defined(_WIN32)
    // On Windows, SIGSEGV/SIGILL/SIGFPE are translated from SEH hardware exceptions
    // by the CRT via a Vectored Exception Handler (VEH). Registering C signal handlers
    // for these causes that VEH to intercept them before SetUnhandledExceptionFilter
    // fires, which loses the EXCEPTION_POINTERS context needed for a useful minidump
    // and accurate stack trace. Only SIGABRT is registered here since abort() raises
    // it explicitly rather than through SEH.
    std::signal( SIGABRT, signal_handler );
    SetUnhandledExceptionFilter( windows_exception_filter );
#else
    for( auto sig : {
             SIGSEGV, SIGILL, SIGABRT,
#if defined(SIGBUS)
             SIGBUS,
#endif
#if defined(SIGTRAP)
             SIGTRAP,
#endif
             SIGFPE
         } ) {
        std::signal( sig, signal_handler );
    }
#endif
    std::set_terminate( crash_terminate_handler );
}

#else // !BACKTRACE

void init_crash_handlers()
{
}

#endif
