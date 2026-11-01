#pragma once

#include <string>

#include "music.h"

#if defined(SDL_SOUND)

/**
 * Attempt to initialize an audio device.  Returns false if initialization fails.
 */
bool init_sound();
void shutdown_sound();
void play_music( const std::string &playlist );
/// Play the playlist named after a dynamic-music context, falling back to "title".
void play_music_context( music::context ctx );
/// Whether this playlist, and not another, owns the currently playing track.
bool music_playlist_playing( const std::string &playlist );
/// Advance a finished track and release its audio. Call from the main thread.
void process_music_events();
void stop_music();
void update_volumes();
void load_soundset();

#else

inline bool init_sound()
{
    return false;
}
inline void shutdown_sound() { }
inline void play_music( const std::string &/*playlist*/ )
{
}
inline void play_music_context( music::context /*ctx*/ ) { }
inline bool music_playlist_playing( const std::string &/*playlist*/ )
{
    return false;
}
inline void process_music_events() { }
inline void stop_music() { }
inline void update_volumes() { }
inline void load_soundset() { }

#endif
