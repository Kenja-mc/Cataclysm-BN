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
void play_music_context( music::context ctx );
bool music_playlist_playing( const std::string &playlist );
bool music_has_playlist( const std::string &playlist );
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
inline bool music_has_playlist( const std::string &/*playlist*/ )
{
    return false;
}
inline void process_music_events() { }
inline void stop_music() { }
inline void update_volumes() { }
inline void load_soundset() { }

#endif
