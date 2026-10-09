#include "first_tips.h"

#include <functional>
#include <string>
#include <vector>

#include "action.h"
#include "avatar.h"
#include "bodypart.h"
#include "calendar.h"
#include "color.h"
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
};

auto key( const action_id act ) -> std::string
{
    return press_x( act, "", "", _( "(unbound)" ) );
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
            [] { return string_format( _( "Something hostile is in sight.  %s attacks the nearest enemy; walking away works too." ), key( ACTION_AUTOATTACK ) ); }
        },
        {
            "hungry", []( const avatar & you ) { return you.get_hunger_description().second == c_yellow; },
            [] { return string_format( _( "You are getting hungry.  %s eats; the sidebar shows how hungry you are." ), key( ACTION_EAT ) ); }
        },
        {
            "thirsty", []( const avatar & you ) { return you.get_thirst() > thirst_levels::thirsty; },
            [] { return string_format( _( "You are getting thirsty.  %s drinks too.  Water from rivers and toilets needs boiling first." ), key( ACTION_EAT ) ); }
        },
        {
            "tired", []( const avatar & you ) { return you.get_fatigue() > fatigue_levels::tired; },
            [] { return string_format( _( "You are tired.  %s sleeps; a bed and a closed door make it safer." ), key( ACTION_SLEEP ) ); }
        },
        {
            "hurt", hurt,
            [] { return string_format( _( "You are hurt.  Wounds heal slowly with rest; bandages and first aid kits work faster (%s)." ), key( ACTION_USE ) ); }
        },
        {
            "heavy", []( const avatar & you ) { return you.weight_carried() > you.weight_capacity(); },
            [] { return string_format( _( "You carry more than you can and move slowly.  %s drops things." ), key( ACTION_DROP ) ); }
        },
        {
            "night", []( const avatar & ) { return is_night( calendar::turn ); },
            [] { return _( "Night has fallen.  You see less, but so do most zombies.  A light helps you and gives you away." ); }
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
        const auto seen = std::string( "tip_seen_" ) + t.id;
        if( you.get_value( seen ).empty() && t.applies( you ) ) {
            you.set_value( seen, "1" );
            add_msg( game_message_params{ m_info, gmf_bypass_cooldown }, _( "Tip: %s" ), t.text() );
            return;
        }
    }
}

} // namespace first_tips
