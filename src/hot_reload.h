#pragma once

/// Live C++ reloading for `CATA_HOT_RELOAD` development builds, through jet-live.
/// Every function is a no-op in other builds.
namespace hot_reload
{

/// Whether this build can reload code.
auto available() -> bool;
/// Starts indexing the program and watching its sources in the background.
auto init() -> void;
/// Polls background compiles and runs a reload requested with SIGUSR1. Main thread only.
auto update() -> void;
/// Recompiles the changed sources and patches them into the running game.
auto reload_now() -> void;

} // namespace hot_reload
