#include "music.h"

#include <chrono>
#include <string>

#include "avatar.h"
#include "calendar.h"
#include "cached_options.h"
#include "game.h"
#include "map/map.h"
#include "options.h"
#include "sdlsound.h"

namespace music
{
namespace
{

auto highest_priority_context( const signals &state ) -> context
{
    if( state.danger && !state.sleeping ) {
        return context::danger;
    }
    if( state.vehicle ) {
        return context::vehicle;
    }
    if( state.underground ) {
        return context::underground;
    }
    if( state.night ) {
        return context::night;
    }
    if( state.shelter ) {
        return context::shelter;
    }
    return context::explore;
}

scheduler game_scheduler;
bool in_game = false;

auto read_signals() -> signals
{
    const avatar &you = get_avatar();
    signals state;
    state.danger = you.get_mon_visible().combat_hostile_count > 0;
    state.vehicle = you.in_vehicle || you.controlling_vehicle;
    state.underground = g->get_levz() < 0;
    state.night = is_night( calendar::turn );
    state.shelter = !get_map().is_outside( you.bub_pos() );
    state.sleeping = you.in_sleep_state();
    return state;
}

}

auto context_id( const context ctx ) -> const char *
{
    switch( ctx ) {
        case context::title:
            return "title";
        case context::explore:
            return "explore";
        case context::danger:
            return "danger";
        case context::night:
            return "night";
        case context::underground:
            return "underground";
        case context::vehicle:
            return "vehicle";
        case context::shelter:
            return "shelter";
    }
    return "title";
}

scheduler::scheduler( timing t ) : timing_( t ) {}

auto scheduler::priority_context( const signals &state ) const -> context
{
    return highest_priority_context( state );
}

auto scheduler::switch_to( const context next, const std::chrono::steady_clock::time_point now )
-> void
{
    current_ = next;
    candidate_ = next;
    changed_at_ = now;
    candidate_since_ = now;
    danger_clearing_ = false;
    changed_ = true;
}

auto scheduler::update( const signals &state, const std::chrono::steady_clock::time_point now )
-> context
{
    changed_ = false;
    const context wanted = priority_context( state );

    if( !started_ ) {
        started_ = true;
        switch_to( wanted, now );
        return current_;
    }

    if( wanted == current_ ) {
        danger_clearing_ = false;
        candidate_ = current_;
        return current_;
    }

    if( state.sleeping && current_ == context::danger ) {
        switch_to( wanted, now );
        return current_;
    }

    if( wanted == context::danger ) {
        danger_clearing_ = false;
        if( current_ != context::danger ) {
            switch_to( wanted, now );
        }
        return current_;
    }

    if( current_ == context::danger ) {
        if( !danger_clearing_ ) {
            danger_clearing_ = true;
            danger_clear_since_ = now;
        }
        if( now - danger_clear_since_ < timing_.danger_release ) {
            return current_;
        }
    } else {
        danger_clearing_ = false;
    }

    if( candidate_ != wanted ) {
        candidate_ = wanted;
        candidate_since_ = now;
    }
    if( now - candidate_since_ >= timing_.candidate_hold &&
        now - changed_at_ >= timing_.minimum_play ) {
        switch_to( wanted, now );
    }
    return current_;
}

auto scheduler::reset() -> void
{
    current_ = context::title;
    candidate_ = context::title;
    changed_at_ = {};
    candidate_since_ = {};
    danger_clear_since_ = {};
    danger_clearing_ = false;
    started_ = false;
    changed_ = false;
}

auto resolve_playlist( const context ctx,
                       const std::function<bool( const std::string & )> &has_playlist ) -> std::string
{
    if( ctx == context::title ) {
        return "title";
    }
    const std::string id = context_id( ctx );
    return has_playlist( id ) ? id : std::string( "title" );
}

auto pump() -> void
{
    process_music_events();
}

auto danger_music_active() -> bool
{
    if( test_mode || !in_game || !get_option<bool>( "DYNAMIC_MUSIC" ) ) {
        return false;
    }
    return game_scheduler.current() == context::danger &&
           music_playlist_playing( "danger" );
}

auto update( const bool force ) -> void
{
    if( test_mode || !g ) {
        return;
    }
    pump();
    in_game = true;

    if( !get_option<bool>( "DYNAMIC_MUSIC" ) ) {
        play_music( "title" );
        return;
    }

    const context selected =
        game_scheduler.update( read_signals(), std::chrono::steady_clock::now() );
    if( force || game_scheduler.changed() ) {
        play_music_context( selected );
    }
}

auto resume() -> void
{
    if( test_mode ) {
        return;
    }
    pump();
    if( in_game ) {
        update( true );
    } else {
        play_music( "title" );
    }
}

auto reset() -> void
{
    game_scheduler.reset();
    in_game = false;
}

auto current_context() -> context
{
    if( !in_game || test_mode || !get_option<bool>( "DYNAMIC_MUSIC" ) ) {
        return context::title;
    }
    return game_scheduler.current();
}

auto current_playlist() -> std::string
{
    return resolve_playlist( current_context(), music_has_playlist );
}

}
