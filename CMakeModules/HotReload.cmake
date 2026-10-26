# CATA_HOT_RELOAD: development-only live C++ reloading with jet-live (https://github.com/ddovod/jet-live).
# Included before add_subdirectory(src) so the flags and the library reach every game target.
option(CATA_HOT_RELOAD "Development only: patch changed C++ into the running game (Linux x86-64, Debug)." "OFF")

if (NOT CATA_HOT_RELOAD)
    return()
endif ()

if (NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR NOT CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|AMD64")
    message(FATAL_ERROR "CATA_HOT_RELOAD supports Linux x86-64 only.")
endif ()
if (NOT CMAKE_BUILD_TYPE STREQUAL "Debug")
    message(FATAL_ERROR "CATA_HOT_RELOAD needs CMAKE_BUILD_TYPE=Debug; use a *-hotreload preset.")
endif ()

FetchContent_Declare(
        jet_live
        GIT_REPOSITORY https://github.com/ddovod/jet-live.git
        GIT_TAG 394948ee312d83c75ca415ff9042d664678f7b38
)
# Skip jet-live's own setup file: it would rewrite the global flags; the ones it needs are below.
set(JET_LIVE_CONFIGURED ON)
set(JET_LIVE_BUILD_EXAMPLE OFF)
FetchContent_MakeAvailable(jet_live)

# Every function needs room for the patch jump, and the reload library resolves symbols against the
# executable.
add_compile_options(-falign-functions=16)
add_link_options(-Wl,-export-dynamic)
add_definitions(-DCATA_HOT_RELOAD)
# Directory-wide so src/CMakeLists.txt stays as upstream has it.
link_libraries(jet-live)

message(STATUS "Hot reload (jet-live)        : ON")
