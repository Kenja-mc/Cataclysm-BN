#include "first_tips.h"

#include <functional>
#include <string>
#include <utility>
#include <vector>

#include "action.h"
#include "avatar.h"
#include "bodypart.h"
#include "calendar.h"
#include "color.h"
#include "input.h"
#include "map/map.h"
#include "map/mapdata.h"
#include "messages.h"
#include "options.h"
#include "string_formatter.h"
#include "translations.h"

namespace
{

struct tip {
    const char *id;
    std::function<bool( const avatar & )> applies;
    std::function<std::string()> text;
    /// The avatar value that records this tip as seen, derived from `id`.
    std::string seen_key;

    tip( const char *id_in, std::function<bool( const avatar & )> applies_in,
         std::function<std::string()> text_in )
        : id( id_in ), applies( std::move( applies_in ) ), text( std::move( text_in ) ),
          seen_key( std::string( "tip_seen_" ) + id ) {}
};

auto key( const action_id act ) -> std::string
{
    if( const auto bound = press_x( act, "", "", "" ); !bound.empty() ) {
        return bound;
    }
    if( act == ACTION_EAT || act == ACTION_USE || act == ACTION_DROP ) {
        return string_format( _( "%s → item actions" ),
                              press_x( ACTION_INVENTORY, "", "", _( "Inventory" ) ) );
    }
    if( act == ACTION_SLEEP ) {
        return string_format( _( "%s → Sleep" ), press_x( ACTION_WAIT, "", "", _( "Wait menu" ) ) );
    }
    return _( "(unbound)" );
}

auto hurt( const avatar &you ) -> bool
{
    for( const auto &bp : you.get_all_body_parts() ) {
        if( you.get_part_hp_cur( bp ) < you.get_part_hp_max( bp ) * 3 / 4 ) {
            return true;
        }
    }
    return false;
}

auto tips() -> const std::vector<tip> & // *NOPAD*
{
    static const auto all = std::vector<tip> {
        {
            "hostile", []( const avatar & you ) { return !you.get_hostile_creatures( 15 ).empty(); },
            [] {
                if( get_option<bool>( "BUMP_ATTACK" ) )
                {
                    return std::string(
                        _( "Something hostile is in sight.  Walk into an adjacent enemy to attack; walking away works too." ) );
                }
                if( get_option<std::string>( "CONTROL_SCHEME" ) == "modern" )
            {
                const auto ctxt = input_context( "DEFAULTMODE" );
                    return string_format(
                        _( "Something hostile is in sight.  Select it with %1$s, then attack with %2$s; walking away works too." ),
                        ctxt.get_desc( "NEXT_TARGET" ), key( ACTION_FIRE ) );
                }
            const auto attack = press_x( ACTION_ATTACK, "", "", "" );
            if( !attack.empty() )
        {
            return string_format(
                _( "Something hostile is in sight.  %s attacks in a direction; walking away works too." ), attack );
            }
            return std::string( _( "Something hostile is in sight.  Bump attacks are disabled; bind the directional attack command or keep your distance." ) );
            }
        },
        {
            "hungry", []( const avatar & you ) { return you.get_hunger_description().second == c_yellow; },
            [] { return string_format( _( "You are getting hungry.  Eat food (%s); the sidebar shows how hungry you are." ), key( ACTION_EAT ) ); }
        },
        {
            "thirsty", []( const avatar & you ) { return you.get_thirst() > thirst_levels::thirsty; },
            [] { return string_format( _( "You are getting thirsty.  Drink (%s).  Water from rivers and toilets needs boiling first." ), key( ACTION_EAT ) ); }
        },
        {
            "tired", []( const avatar & you ) { return you.get_fatigue() > fatigue_levels::tired; },
            [] { return string_format( _( "You are tired.  Sleep (%s); a bed and a closed door make it safer." ), key( ACTION_SLEEP ) ); }
        },
        {
            "hurt", hurt,
            [] { return string_format( _( "You are hurt.  Wounds heal slowly with rest; bandages and first aid kits work faster (%s)." ), key( ACTION_USE ) ); }
        },
        {
            "heavy", []( const avatar & you ) { return you.weight_carried() > you.weight_capacity(); },
            [] { return string_format( _( "You carry more than you can and move slowly.  Drop items (%s)." ), key( ACTION_DROP ) ); }
        },
        {
            "stairs",
            []( const avatar & you ) {
                const auto &here = get_map();
                return here.has_flag( TFLAG_GOES_UP, you.bub_pos() ) ||
                       here.has_flag( TFLAG_GOES_DOWN, you.bub_pos() );
            },
            [] {
                const auto ctxt = input_context( "DEFAULTMODE" );
                return string_format( _( "You are standing on stairs.  %1$s goes up, %2$s goes down." ),
                                      ctxt.get_desc( "LEVEL_UP" ), ctxt.get_desc( "LEVEL_DOWN" ) );
            }
        },
        {
            "save",
            []( const avatar & /*you*/ ) { return calendar::turn - calendar::start_of_game > 5_turns; },
            [] {
                return _( "The game saves for you: it autosaves as you play, and saves when you quit." );
            }
        },
        {
            "night", []( const avatar & ) { return is_night( calendar::turn ); },
            [] { return _( "Night has fallen.  You see less, but so do most zombies.  A light helps you and gives you away." ); }
        },
        {
            "goal",
            []( const avatar & /*you*/ ) { return calendar::turn - calendar::start_of_game > 5_minutes; },
            [] {
                const auto explore = press_x( ACTION_AUTO_EXPLORE, "", "", "" );
                return string_format( _( "Start by finding water, food and a weapon; houses usually have all three.  "
                                         "%s opens the map." ), key( ACTION_MAP ) ) +
                       ( explore.empty() ? std::string() :
                         string_format( _( "  %s walks toward ground you have not seen yet." ), explore ) );
            }
        },
    };
    return all;
}

} // namespace

namespace first_tips
{

auto check( avatar &you ) -> void
{
    if( !get_option<bool>( "SHOW_TIPS" ) ) {
        return;
    }
    for( const auto &t : tips() ) {
        if( you.get_value( t.seen_key ).empty() && t.applies( you ) ) {
            you.set_value( t.seen_key, "1" );
            add_msg( game_message_params{ m_info, gmf_bypass_cooldown }, _( "Tip: %s" ), t.text() );
            return;
        }
    }
}

} // namespace first_tips
