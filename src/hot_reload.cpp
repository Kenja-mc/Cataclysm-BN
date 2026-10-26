#include "hot_reload.h"

#if defined(CATA_HOT_RELOAD)

#include <algorithm>
#include <atomic>
#include <chrono>
#include <csignal>
#include <memory>
#include <string>
#include <thread>

#include <jet/live/Live.hpp>

#include "debug.h"
#include "messages.h"
#include "popup.h"
#include "translations.h"

namespace
{

using namespace std::chrono_literals;

/// A change to a widely included header recompiles hundreds of files.
constexpr auto reload_timeout = 30min;

std::atomic_bool signal_requested = false;
auto reloading = false;
auto pending = false;
auto live = std::unique_ptr<jet::Live>();

auto on_signal( int /*signal*/ ) -> void { signal_requested = true; }

auto debug_level( jet::LogSeverity severity ) -> DL
{
    switch( severity ) {
        case jet::LogSeverity::kDebug:
            return DL::Debug;
        case jet::LogSeverity::kInfo:
            return DL::Info;
        case jet::LogSeverity::kWarning:
            return DL::Warn;
        case jet::LogSeverity::kError:
            return DL::Error;
    }
    return DL::Info;
}

auto first_line( const std::string &text ) -> std::string { return text.substr( 0, text.find( '\n' ) ); }

class listener : public jet::ILiveListener
{
    public:
        void onLog( jet::LogSeverity severity, const std::string &message ) override {
            DebugLog( debug_level( severity ), DC::Main ) << "hot reload: " << message;
            // jet-live reports these outcomes only as log lines.
            if( message == "Nothing to reload." ) {
                add_msg( m_info, _( "Hot reload: no source changed since the last reload." ) );
                pending = false;
            } else if( message == "Code reloaded" ) {
                add_msg( m_good, _( "Hot reload: code reloaded." ) );
            } else if( severity >= jet::LogSeverity::kWarning ) {
                add_msg( m_bad, _( "Hot reload: %s" ), first_line( message ) );
            }
        }
        void onCodePostLoad() override { pending = false; }
};

} // namespace

auto hot_reload::available() -> bool { return true; }

auto hot_reload::init() -> void
{
    if( live ) {
        return;
    }
    live = std::make_unique<jet::Live>( std::make_unique<listener>(), jet::LiveConfig{
        .workerThreadsCount = std::max( 1U, std::thread::hardware_concurrency() ),
        // Our handler only sets a flag, so the reload runs at a safe point on the main thread.
        .reloadOnSignal = false,
    } );
    std::signal( SIGUSR1, on_signal );
}

auto hot_reload::update() -> void
{
    if( !live || reloading ) {
        return;
    }
    live->update();
    if( signal_requested.exchange( false ) ) {
        reload_now();
    }
}

auto hot_reload::reload_now() -> void
{
    if( !live || reloading ) {
        return;
    }
    live->update();
    if( !live->isInitialized() ) {
        add_msg( m_info, _( "Hot reload is still indexing the game; try again shortly." ) );
        return;
    }
    reloading = true;
    pending = true;
    live->tryReload();
    {
        auto popup = throbber_popup( _( "Recompiling changed sources…" ) );
        const auto deadline = std::chrono::steady_clock::now() + reload_timeout;
        while( pending && std::chrono::steady_clock::now() < deadline ) {
            live->update();
            popup.refresh();
            std::this_thread::sleep_for( 10ms );
        }
    }
    if( pending ) {
        add_msg( m_bad, _( "Hot reload timed out." ) );
        pending = false;
    }
    reloading = false;
}

#else

auto hot_reload::available() -> bool { return false; }
auto hot_reload::init() -> void {}
auto hot_reload::update() -> void {}
auto hot_reload::reload_now() -> void {}

#endif
