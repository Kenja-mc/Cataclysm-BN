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
const auto sound_options = std::array<std::string, 5> {
    "SOUND_ENABLED", "MUSIC_ENABLED", "MUSIC_VOLUME", "SOUND_EFFECT_VOLUME", "AMBIENT_SOUND_VOLUME"
};
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
    menu.addentry( 0, true, 0, _( "Sound" ) );
    menu.addentry( 1, true, 0, _( "Music" ) );
    menu.addentry( 2, true, 0, _( "Music volume" ) );
    menu.addentry( 3, true, 0, _( "Sound effect volume" ) );
    menu.addentry( 4, true, 0, _( "Ambient volume" ) );

    const auto refresh_value = [&]( const int row ) {
        if( row < 2 ) {
            menu.entries[row].ctxt = get_option<bool>( sound_options[row] ) ? _( "On" ) : _( "Off" );
        } else {
            const auto volume = get_option<int>( sound_options[row] );
            menu.entries[row].ctxt = string_format( "%3d%%", ( volume * 100 + volume_max / 2 ) / volume_max );
        }
    };
    for( auto row = 0; row < static_cast<int>( sound_options.size() ); ++row ) {
        refresh_value( row );
    }

    while( true ) {
        menu.query();
        if( menu.ret == UILIST_CANCEL || menu.ret == UILIST_ERROR ) {
            break;
        }
        const auto row = menu.selected;
        auto &option = get_options().get_option( sound_options[row] );
        if( row < 2 ) {
            const auto before = get_option<bool>( sound_options[row] );
            const auto after = menu.ret == UILIST_ADDITIONAL ? menu.ret_act == "RIGHT" : !before;
            if( before == after ) {
                continue;
            }
            option.setValue( std::string( after ? "true" : "false" ) );
        } else {
            const auto before = get_option<int>( sound_options[row] );
            const auto delta = menu.ret_act == "LEFT" ? -volume_step : volume_step;
            const auto after = std::clamp( before + delta, 0, volume_max );
            if( before == after ) {
                continue;
            }
            option.setValue( after );
        }
        update_volumes();
        if( row == 3 ) {
            sfx::play_variant_sound( "menu_move", "default", 100 );
        }
        refresh_value( row );
    }
    get_options().save();
#else
    // A modal here steals input from a player whose build has no sound device.
    if( g && g->w_terrain ) {
        add_msg( m_info, _( "Sound is unavailable in this build." ) );
    } else {
        popup( _( "Sound is unavailable in this build." ) );
    }
#endif
}
