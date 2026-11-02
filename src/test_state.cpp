#include "test_state.h"

#include <algorithm>
#include <iterator>
#include <optional>
#include <string>
#include <vector>

#include "avatar.h"
#include "calendar.h"
#include "coordinates.h"
#include "fstream_utils.h"
#include "hud_snapshot.h"
#include "item.h"
#include "json.h"
#include "map_overlay.h"

namespace
{

struct ui_entry {
    std::string id;
    std::string title;
    std::vector<test_state::row> rows;
    int selected = -1;
};

struct state_data {
    int turn = -1;
    bool input_wait = false;
    std::vector<ui_entry> stack;
    std::string player_name;
    int hp = 0;
    int pos_x = 0;
    int pos_y = 0;
    int pos_z = 0;
    std::string wielded;
    std::vector<std::string> worn;
    int stamina = 0;
    int pain = 0;
    int morale = 0;
    std::optional<hud_snapshot::snapshot> hud;
    std::vector<map_overlay::overlay> map_overlays;
};

std::string state_path;
bool path_set = false;
state_data state;

auto color_value( const nc_color &color ) -> int
{
    return static_cast<int>( color );
}

auto write_need( JsonOut &out, const hud_snapshot::need &need ) -> void
{
    out.start_object();
    out.member( "label", need.label );
    out.member( "text", need.text );
    out.member( "color", color_value( need.color ) );
    out.member( "fine", need.fine );
    out.end_object();
}

auto write_limb( JsonOut &out, const hud_snapshot::limb &limb ) -> void
{
    out.start_object();
    out.member( "name", limb.name );
    out.member( "hp", limb.hp );
    out.member( "hp_max", limb.hp_max );
    out.member( "color", color_value( limb.color ) );
    out.member( "wound", limb.wound );
    out.member( "wound_color", color_value( limb.wound_color ) );
    out.end_object();
}

auto write_sighting( JsonOut &out, const hud_snapshot::sighting &sighting ) -> void
{
    out.start_object();
    out.member( "name", sighting.name );
    out.member( "symbol", sighting.symbol );
    out.member( "color", color_value( sighting.color ) );
    out.member( "direction", sighting.direction );
    out.member( "distance", sighting.distance );
    out.member( "hostile", sighting.hostile );
    out.end_object();
}

auto write_carried( JsonOut &out, const hud_snapshot::carried &carried ) -> void
{
    out.start_object();
    out.member( "name", carried.name );
    out.member( "symbol", carried.symbol );
    out.member( "color", color_value( carried.color ) );
    out.member( "detail", carried.detail );
    out.end_object();
}

auto write_hud( JsonOut &out, const hud_snapshot::snapshot &hud ) -> void
{
    out.start_object();
    out.member( "time", hud.time );
    out.member( "date", hud.date );
    out.member( "weather", hud.weather );
    out.member( "weather_color", color_value( hud.weather_color ) );
    out.member( "light", hud.light );
    out.member( "light_color", color_value( hud.light_color ) );
    out.member( "wind", hud.wind );
    out.member( "wind_color", color_value( hud.wind_color ) );
    out.member( "place", hud.place );
    out.member( "underground", hud.underground );
    out.member( "hp_percent", hud.hp_percent );
    out.member( "hp_color", color_value( hud.hp_color ) );
    out.member( "stamina", hud.stamina );
    out.member( "stamina_max", hud.stamina_max );
    out.member( "focus", hud.focus );
    out.member( "morale", hud.morale );
    out.member( "speed", hud.speed );
    out.member( "pain_level", hud.pain_level );
    out.member( "move_counter", hud.move_counter );
    out.member( "stance", hud.stance );
    out.member( "stance_color", color_value( hud.stance_color ) );
    out.member( "sound", hud.sound );

    out.member( "pain" );
    write_need( out, hud.pain );
    out.member( "thirst" );
    write_need( out, hud.thirst );
    out.member( "hunger" );
    write_need( out, hud.hunger );
    out.member( "rest" );
    write_need( out, hud.rest );
    out.member( "heat" );
    write_need( out, hud.heat );

    out.member( "weapon", hud.weapon );
    out.member( "armed", hud.armed );
    out.member( "gun", hud.gun );
    out.member( "ammo", hud.ammo );
    out.member( "weapon_symbol", hud.weapon_symbol );
    out.member( "weapon_color", color_value( hud.weapon_color ) );
    out.member( "style", hud.style );

    out.member( "weight", hud.weight );
    out.member( "volume", hud.volume );
    out.member( "weight_kg", hud.weight_kg );
    out.member( "volume_l", hud.volume_l );
    out.member( "weight_color", color_value( hud.weight_color ) );
    out.member( "volume_color", color_value( hud.volume_color ) );

    out.member( "safe_mode", hud.safe_mode );
    out.member( "safe_color", color_value( hud.safe_color ) );

    out.member( "str", hud.str );
    out.member( "dex", hud.dex );
    out.member( "intel", hud.intel );
    out.member( "per", hud.per );

    out.member( "limbs" );
    out.start_array();
    for( const auto &limb : hud.limbs ) {
        write_limb( out, limb );
    }
    out.end_array();

    out.member( "log" );
    out.write( hud.log );

    out.member( "seen" );
    out.start_array();
    for( const auto &sighting : hud.seen ) {
        write_sighting( out, sighting );
    }
    out.end_array();

    out.member( "loadout" );
    out.start_array();
    for( const auto &carried : hud.loadout ) {
        write_carried( out, carried );
    }
    out.end_array();
    out.end_object();
}

auto write_state( std::ostream &stream ) -> void
{
    JsonOut out( stream );
    out.start_object();
    out.member( "turn", state.turn );
    out.member( "input_wait", state.input_wait );

    out.member( "ui" );
    out.start_object();
    out.member( "stack" );
    out.start_array();
    for( const auto &entry : state.stack ) {
        out.start_object();
        out.member( "id", entry.id );
        out.member( "title", entry.title );
        out.end_object();
    }
    out.end_array();
    if( state.stack.empty() ) {
        out.null_member( "top" );
    } else {
        const auto &top = state.stack.back();
        out.member( "top" );
        out.start_object();
        out.member( "id", top.id );
        out.member( "title", top.title );
        out.member( "rows" );
        out.start_array();
        for( const auto &row : top.rows ) {
            out.start_object();
            out.member( "text", row.text );
            out.member( "hotkey", row.hotkey );
            out.member( "enabled", row.enabled );
            out.end_object();
        }
        out.end_array();
        out.member( "selected", top.selected );
        out.end_object();
    }
    out.end_object();

    out.member( "player" );
    out.start_object();
    out.member( "name", state.player_name );
    out.member( "hp", state.hp );
    out.member( "pos" );
    out.start_array();
    out.write( state.pos_x );
    out.write( state.pos_y );
    out.write( state.pos_z );
    out.end_array();
    out.member( "wielded", state.wielded );
    out.member( "worn" );
    out.write( state.worn );
    out.member( "stamina", state.stamina );
    out.member( "pain", state.pain );
    out.member( "morale", state.morale );
    out.end_object();

    out.member( "hud" );
    if( state.hud ) {
        write_hud( out, *state.hud );
    } else {
        out.start_object();
        out.end_object();
    }

    out.member( "map_overlays" );
    out.start_array();
    for( const auto &overlay : state.map_overlays ) {
        out.start_object();
        out.member( "pos" );
        out.start_array();
        out.write( overlay.pos.x() );
        out.write( overlay.pos.y() );
        out.write( overlay.pos.z() );
        out.end_array();
        out.member( "kind", map_overlay::kind_name( overlay.kind ) );
        out.member( "age", overlay.age );
        out.member( "severity", overlay.severity );
        out.member( "label", overlay.label );
        out.end_object();
    }
    out.end_array();
    out.end_object();
}

auto flush() -> void
{
    if( !path_set ) {
        return;
    }
    write_to_file( state_path, []( std::ostream & stream ) {
        write_state( stream );
    }, "" );
}

}

namespace test_state
{

auto set_path( const std::string &path ) -> void
{
    state_path = path;
    path_set = !path.empty();
}

auto enabled() -> bool
{
    return path_set;
}

auto on_turn( const avatar &you ) -> void
{
    if( !path_set ) {
        return;
    }
    state.turn = to_turn<int>( calendar::turn );
    state.player_name = you.get_name();
    state.hp = you.get_hp();
    const tripoint_bub_ms where = you.bub_pos();
    state.pos_x = where.x();
    state.pos_y = where.y();
    state.pos_z = where.z();
    const item &weapon = you.primary_weapon();
    state.wielded = weapon.is_null() ? std::string() : weapon.tname();
    state.worn.clear();
    for( const auto &worn : you.worn ) {
        state.worn.push_back( worn->tname() );
    }
    state.stamina = you.get_stamina();
    state.pain = you.get_pain();
    state.morale = you.get_morale_level();
    state.hud = hud_snapshot::read( you );
    state.map_overlays = map_overlay::collect( you );
    flush();
}

auto refresh_overlays( const avatar &you ) -> void
{
    if( !path_set ) {
        return;
    }
    state.map_overlays = map_overlay::collect( you );
    flush();
}

auto input_wait( bool waiting ) -> void
{
    if( !path_set || state.input_wait == waiting ) {
        return;
    }
    state.input_wait = waiting;
    flush();
}

auto ui_show( const std::string &id, const std::string &title,
              const std::vector<row> &rows, int selected ) -> void
{
    if( !path_set ) {
        return;
    }
    if( state.stack.empty() || state.stack.back().id != id ) {
        state.stack.push_back( ui_entry{ .id = id, .title = title } );
    }
    auto &top = state.stack.back();
    top.title = title;
    top.rows = rows;
    top.selected = selected;
    flush();
}

auto ui_close( const std::string &id ) -> void
{
    if( !path_set ) {
        return;
    }
    const auto found = std::find_if( state.stack.rbegin(), state.stack.rend(),
    [&id]( const ui_entry & entry ) {
        return entry.id == id;
    } );
    if( found == state.stack.rend() ) {
        return;
    }
    state.stack.erase( std::next( found ).base() );
    flush();
}

}
