#include "sound_menu.h"

#include "output.h"
#include "translations.h"

#if !defined(SDL_SOUND)
#include "game.h"
#include "messages.h"
#endif

#if defined(SDL_SOUND)
#include <algorithm>
#include <array>
#include <string>

#include "options.h"
#include "sdlsound.h"
#include "sounds.h"
#include "string_formatter.h"
#include "ui.h"

namespace
{
struct sound_row {
    std::string option;
    const char *label;
    bool toggle;
};
const auto sound_rows = std::array<sound_row, 8> { {
        { "SOUND_ENABLED", translate_marker( "Sound" ), true },
        { "MUSIC_ENABLED", translate_marker( "Music" ), true },
        { "DYNAMIC_MUSIC", translate_marker( "Music follows the game state" ), true },
        { "MUSIC_VOLUME", translate_marker( "Music volume" ), false },
        { "SOUND_EFFECT_VOLUME", translate_marker( "Sound effect volume" ), false },
        { "AMBIENT_SOUND_VOLUME", translate_marker( "Ambient volume" ), false },
        { "MONSTER_AMBIENCE", translate_marker( "Monster ambience" ), true },
        { "MONSTER_AMBIENCE_VOLUME", translate_marker( "Monster ambience volume" ), false },
    } };
constexpr auto volume_step = 8;
constexpr auto volume_max = 128;
} // namespace
#endif

auto show_sound_menu() -> void
{
#if defined(SDL_SOUND)
    auto menu = uilist();
    menu.title = _( "Sound & volume" );
    menu.text =
        _( "Left/Right adjusts; Enter or click increases or toggles.\nChanges apply immediately.  Close to save." );
    menu.w_width_setup = 58;
    menu.filtering = false;
    menu.allow_additional = true;
    menu.additional_actions = {
        { "LEFT", translation() },
        { "RIGHT", translation() }
    };
    for( auto row = 0; row < static_cast<int>( sound_rows.size() ); ++row ) {
        menu.addentry( row, true, 0, _( sound_rows[row].label ) );
    }

    const auto refresh_value = [&]( const int row ) {
        const auto &entry = sound_rows[row];
        if( entry.toggle ) {
            menu.entries[row].ctxt = get_option<bool>( entry.option ) ? _( "On" ) : _( "Off" );
        } else {
            const auto volume = get_option<int>( entry.option );
            menu.entries[row].ctxt = string_format( "%3d%%", ( volume * 100 + volume_max / 2 ) / volume_max );
        }
    };
    for( auto row = 0; row < static_cast<int>( sound_rows.size() ); ++row ) {
        refresh_value( row );
    }

    while( true ) {
        menu.query();
        if( menu.ret == UILIST_CANCEL || menu.ret == UILIST_ERROR ) {
            break;
        }
        const auto row = menu.selected;
        const auto &entry = sound_rows[row];
        auto &option = get_options().get_option( entry.option );
        if( entry.toggle ) {
            const auto before = get_option<bool>( entry.option );
            const auto after = menu.ret == UILIST_ADDITIONAL ? menu.ret_act == "RIGHT" : !before;
            if( before == after ) {
                continue;
            }
            option.setValue( std::string( after ? "true" : "false" ) );
        } else {
            const auto before = get_option<int>( entry.option );
            const auto delta = menu.ret_act == "LEFT" ? -volume_step : volume_step;
            const auto after = std::clamp( before + delta, 0, volume_max );
            if( before == after ) {
                continue;
            }
            option.setValue( after );
        }
        update_volumes();
        if( entry.option == "SOUND_EFFECT_VOLUME" ) {
            sfx::play_variant_sound( "menu_move", "default", 100 );
        }
        refresh_value( row );
    }
    get_options().save();
#else
    // One modal teaches the player their build has no sound; repeating it steals input.
    static auto announced = false;
    if( !announced ) {
        announced = true;
        popup( _( "Sound is unavailable in this build." ) );
    } else if( g && g->w_terrain ) {
        add_msg( m_info, _( "Sound is unavailable in this build." ) );
    }
#endif
}
