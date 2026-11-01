#include "world_hub.h"

#include <algorithm>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "avatar.h"
#include "catacharset.h"
#include "cata_utility.h"
#include "clzones.h"
#include "color.h"
#include "coordinates.h"
#include "cursesdef.h"
#include "faction.h"
#include "game.h"
#include "input.h"
#include "line.h"
#include "map/map.h"
#include "options.h"
#include "output.h"
#include "overmap/overmap_ui.h"
#include "point.h"
#include "popup.h"
#include "scrollbar_input.h"
#include "string_formatter.h"
#include "translations.h"
#include "ui.h"

namespace
{

/// The World page's Zones tab. The zone manager keeps the map; this tab shows the same zones,
/// their details and every zone action on one page.
class zones_panel : public world_hub::panel
{
    public:
        zones_panel() {
            // The page binds none of these; the zone screen's own context carries their keys.
            zones_ctxt.register_action( "ADD_ZONE" );
            zones_ctxt.register_action( "REMOVE_ZONE" );
            zones_ctxt.register_action( "MOVE_ZONE_UP" );
            zones_ctxt.register_action( "MOVE_ZONE_DOWN" );
            zones_ctxt.register_action( "SHOW_ZONE_ON_MAP" );
            zones_ctxt.register_action( "ENABLE_ZONE" );
            zones_ctxt.register_action( "DISABLE_ZONE" );
            zones_ctxt.register_action( "SHOW_ALL_ZONES" );
            zones_ctxt.register_action( "TOGGLE_ZONE_OVERLAY" );
            // debug_submap_grid lives in DEFAULTMODE, so resolve it from that context.
            debug_ctxt.register_action( "debug_submap_grid" );
            // The zone tile overlays follow the same flag the standalone manager uses.
            g->set_zones_manager_open( true );
        }

        auto name() const -> std::string override {
            return _( "Zones" );
        }
        void refresh() override;
        void draw( const catacurses::window &body, input_context &ctxt ) override;
        void handle( const std::string &action, input_context &ctxt,
                     const catacurses::window &body, world_hub::host &page ) override;
        void close() override;

    private:
        auto visible_zones() -> std::vector<zone_manager::ref_zone_data>;
        auto query_position( world_hub::host &page )
        -> std::optional<std::pair<tripoint_abs_ms, tripoint_abs_ms>>;
        void add_zone( world_hub::host &page );
        void edit_selected( world_hub::host &page );

        input_context zones_ctxt{ "ZONES_MANAGER" };
        input_context debug_ctxt{ "DEFAULTMODE" };
        std::vector<zone_manager::ref_zone_data> zones;
        int active_index = 0;
        int rows_visible = 0;
        int top_index = 0;
        std::optional<size_t> mouse_row;
        bool show_all = false;
        bool dirty = false;
};

auto zones_panel::visible_zones() -> std::vector<zone_manager::ref_zone_data>
{
    auto &mgr = zone_manager::get_manager();
    if( show_all ) {
        return mgr.get_zones();
    }
    std::vector<zone_manager::ref_zone_data> result;
    const tripoint_abs_ms u_abs_pos = get_avatar().abs_pos();
    for( zone_manager::ref_zone_data &ref : mgr.get_zones() ) {
        const tripoint_abs_ms zone_abs_pos = ref.get().get_center_point();
        if( u_abs_pos.z() == zone_abs_pos.z() && rl_dist( u_abs_pos, zone_abs_pos ) <= 50 ) {
            result.emplace_back( ref );
        }
    }
    return result;
}

void zones_panel::refresh()
{
    zones = visible_zones();
    if( zones.empty() ) {
        active_index = 0;
    } else if( active_index < 0 ) {
        active_index = 0;
    } else if( active_index >= static_cast<int>( zones.size() ) ) {
        active_index = static_cast<int>( zones.size() ) - 1;
    }
}

void zones_panel::draw( const catacurses::window &body, input_context & )
{
    werase( body );
    const int height = getmaxy( body );
    draw_border( body );

    const std::string title = string_format( _( "Zones (%d)" ), static_cast<int>( zones.size() ) );
    mvwprintz( body, point( 2, 0 ), c_white, title );
    mvwprintz( body, point( 2 + utf8_width( title ) + 2, 0 ), c_dark_gray,
               show_all ? _( "showing every zone" ) : _( "showing zones nearby" ) );

    const int list_width = 30;
    for( int y = 2; y < height - 5; ++y ) {
        mvwputch( body, point( list_width, y ), BORDER_COLOR, LINE_XOXO );
    }

    const int rows = std::max( 0, height - 8 );
    rows_visible = rows;
    if( zones.empty() ) {
        top_index = 0;
        mvwprintz( body, point( 2, 3 ), c_white, _( "No zones here." ) );
    } else {
        int top = active_index - rows / 2;
        top = std::max( top, 0 );
        top = std::min( top, std::max( 0, static_cast<int>( zones.size() ) - rows ) );
        top_index = top;
        if( rows > 0 ) {
            draw_scrollbar( body, active_index, rows, static_cast<int>( zones.size() ),
                            point( 0, 2 ) );
        }
        for( int i = 0; i < rows; ++i ) {
            const int index = top + i;
            if( index >= static_cast<int>( zones.size() ) ) {
                break;
            }
            const zone_data &zone = zones[index].get();
            const nc_color color = zone.get_enabled() ? c_white : c_dark_gray;
            const int y = 2 + i;
            if( index == active_index ) {
                mvwprintz( body, point( 1, y ), c_light_green, ">" );
            }
            mvwprintz( body, point( 3, y ), index == active_index ? hilite( color ) : color,
                       trim_by_length( zone.get_name(), list_width - 4 ) );
        }

        const zone_data &zone = zones[active_index].get();
        auto &mgr = zone_manager::get_manager();
        int y = 2;
        mvwprintz( body, point( list_width + 2, y ), c_white, zone.get_name() );
        mvwprintz( body, point( list_width + 2, ++y ), c_light_gray,
                   string_format( _( "Type: %s" ), mgr.get_name_from_type( zone.get_type() ) ) );
        mvwprintz( body, point( list_width + 2, ++y ), c_light_gray,
                   zone.get_enabled() ? _( "Enabled" ) : _( "Disabled" ) );
        const tripoint_abs_ms center = zone.get_center_point();
        mvwprintz( body, point( list_width + 2, ++y ), c_light_gray,
                   string_format( _( "Center: %d,%d" ), center.x(), center.y() ) );
        ++y;
        for( const std::pair<std::string, std::string> &option :
             zone.get_options().get_descriptions() ) {
            if( y >= height - 5 ) {
                break;
            }
            mvwprintz( body, point( list_width + 2, y ), c_light_gray, option.first );
            mvwprintz( body, point( list_width + 18, y ), c_light_gray, option.second );
            ++y;
        }
    }

    // Keys come from the zone screen's own context, so renamed bindings stay truthful.
    const auto key = [this]( const std::string &action ) {
        return zones_ctxt.get_desc( action, 1 );
    };
    mvwprintz( body, point( 2, height - 3 ), c_dark_gray,
               string_format( _( "%s add   %s remove   %s enable   %s disable   %s order up   %s order down" ),
                              key( "ADD_ZONE" ), key( "REMOVE_ZONE" ), key( "ENABLE_ZONE" ),
                              key( "DISABLE_ZONE" ), key( "MOVE_ZONE_UP" ), key( "MOVE_ZONE_DOWN" ) ) );
    mvwprintz( body, point( 2, height - 2 ), c_dark_gray,
               string_format( _( "%s edit   %s show on map   %s list every zone   %s overlay" ),
                              key( "CONFIRM" ), key( "SHOW_ZONE_ON_MAP" ),
                              key( "SHOW_ALL_ZONES" ), key( "TOGGLE_ZONE_OVERLAY" ) ) );
    wnoutrefresh( body );
}

auto zones_panel::query_position( world_hub::host &page )
-> std::optional<std::pair<tripoint_abs_ms, tripoint_abs_ms>>
{
    // The map must be visible while the corners are picked.
    page.hide();
    on_out_of_scope restore_page( [&page]() {
        page.restore();
    } );

    static_popup popup;
    popup.on_top( true );
    popup.message( "%s", _( "Select first point." ) );

    tripoint_bub_ms center = get_avatar().bub_pos() + get_avatar().view_offset;
    const look_around_result first = g->look_around( /*show_window=*/false, center, center, false,
                                     true, false );
    if( !first.position ) {
        return std::nullopt;
    }
    popup.message( "%s", _( "Select second point." ) );
    const look_around_result second = g->look_around( /*show_window=*/false, center, *first.position,
                                      true, true, false );
    if( !second.position ) {
        return std::nullopt;
    }
    const tripoint_bub_ms start( std::min( first.position->x(), second.position->x() ),
                                 std::min( first.position->y(), second.position->y() ),
                                 std::min( first.position->z(), second.position->z() ) );
    const tripoint_bub_ms end( std::max( first.position->x(), second.position->x() ),
                               std::max( first.position->y(), second.position->y() ),
                               std::max( first.position->z(), second.position->z() ) );
    return std::pair<tripoint_abs_ms, tripoint_abs_ms>( bub_to_abs( start ), bub_to_abs( end ) );
}

void zones_panel::add_zone( world_hub::host &page )
{
    auto &mgr = zone_manager::get_manager();
    const std::optional<zone_type_id> zone_type = mgr.query_type();
    if( !zone_type.has_value() ) {
        return;
    }
    shared_ptr_fast<zone_options> options = zone_options::create( zone_type.value() );
    if( !options->query_at_creation() ) {
        return;
    }
    std::string default_name = options->get_zone_name_suggestion();
    if( default_name.empty() ) {
        default_name = mgr.get_name_from_type( zone_type.value() );
    }
    const std::optional<std::string> name = mgr.query_name( default_name );
    if( !name.has_value() ) {
        return;
    }
    const auto position = query_position( page );
    if( !position ) {
        return;
    }
    mgr.add( name.value(), zone_type.value(), get_avatar().get_faction()->id, false, true,
             position->first, position->second, options );
    dirty = true;
    // Select the zone that was just added, as the standalone manager does.
    zones = visible_zones();
    active_index = zones.empty() ? 0 : static_cast<int>( zones.size() ) - 1;
}

void zones_panel::edit_selected( world_hub::host &page )
{
    if( zones.empty() ) {
        return;
    }
    zone_data &zone = zones[active_index].get();

    uilist as_m;
    as_m.text = _( "What do you want to change:" );
    as_m.entries.emplace_back( 1, true, '1', _( "Edit name" ) );
    as_m.entries.emplace_back( 2, true, '2', _( "Edit type" ) );
    as_m.entries.emplace_back( 3, zone.get_options().has_options(), '3',
                               zone.get_type() == zone_type_id( "LOOT_CUSTOM" ) ?
                               _( "Edit filter" ) : _( "Edit options" ) );
    as_m.entries.emplace_back( 4, !zone.get_is_vehicle(), '4', _( "Edit position" ) );
    // TODO: Enable moving vzone after vehicle zone can be bigger than 1*1
    as_m.entries.emplace_back( 5, !zone.get_is_vehicle(), '5', _( "Move position" ) );
    as_m.query();

    switch( as_m.ret ) {
        case 1:
            if( zone.set_name() ) {
                dirty = true;
            }
            break;
        case 2:
            if( zone.set_type() ) {
                dirty = true;
            }
            break;
        case 3:
            if( zone.get_options().query() ) {
                dirty = true;
            }
            break;
        case 4: {
            const auto pos = query_position( page );
            if( pos && ( pos->first != zone.get_start_point() ||
                         pos->second != zone.get_end_point() ) ) {
                zone.set_position( *pos );
                dirty = true;
            }
            break;
        }
        case 5: {
            // The map must be visible while the zone is moved.
            page.hide();
            on_out_of_scope restore_page( [&page]() {
                page.restore();
            } );
            static_popup message_pop;
            message_pop.on_top( true );
            message_pop.message( "%s", _( "Moving zone." ) );
            const tripoint_bub_ms zone_local_start_point = abs_to_bub( zone.get_start_point() );
            tripoint_bub_ms view_center = abs_to_bub( zone.get_center_point() );
            const look_around_result result_local = g->look_around( false, view_center,
                zone_local_start_point, false, false, false, true,
                abs_to_bub( zone.get_end_point() ) );
            if( result_local.position ) {
                const tripoint_abs_ms new_start_point = bub_to_abs( *result_local.position );
                if( new_start_point == zone.get_start_point() ) {
                    break; // Nothing changed, don't save
                }
                const tripoint_abs_ms new_end_point = zone.get_end_point() - zone.get_start_point() +
                                                      new_start_point;
                zone.set_position( std::pair<tripoint_abs_ms, tripoint_abs_ms>( new_start_point,
                                   new_end_point ) );
                dirty = true;
            }
            break;
        }
        default:
            break;
    }
}

void zones_panel::handle( const std::string &action, input_context &ctxt,
                          const catacurses::window &body, world_hub::host &page )
{
    std::string act = action;
    const bool modern = get_option<std::string>( "CONTROL_SCHEME" ) == "modern";
    if( modern && ctxt.get_raw_input().type == input_event_t::mouse ) {
        if( act == "SCROLL_UP" || act == "SCROLL_DOWN" ) {
            act = act == "SCROLL_UP" ? "UP" : "DOWN";
            mouse_row.reset();
        } else if( act == "SELECT" || act == "SEC_SELECT" ) {
            bool confirmed_row = false;
            if( const auto mouse = ctxt.get_coordinates( body ) ) {
                const point cell = mouse->xy().raw() + point( getmaxx( body ), getmaxy( body ) ) / 2;
                if( const auto hit = scrollbar_input::click( {
                .offset = point( 0, 2 ),
                .viewport_size = rows_visible,
                .content_size = static_cast<int>( zones.size() ),
                .viewport_pos = active_index,
                .scroll_to_last = true,
                           }, cell ) ) {
                    active_index = hit->viewport_pos;
                    mouse_row.reset();
                } else if( cell.x >= 1 && cell.x < 28 && cell.y >= 2 &&
                           cell.y < 2 + rows_visible ) {
                    const int idx = top_index + cell.y - 2;
                    if( idx >= 0 && idx < static_cast<int>( zones.size() ) ) {
                        if( mouse_row && *mouse_row == static_cast<size_t>( idx ) ) {
                            // A second click on the same row opens its edit menu.
                            active_index = idx;
                            act = "CONFIRM";
                            confirmed_row = true;
                            mouse_row.reset();
                        } else {
                            active_index = idx;
                            mouse_row = static_cast<size_t>( idx );
                        }
                    }
                }
            }
            // Only a row double-click falls through to the action below.
            if( !confirmed_row ) {
                return;
            }
        } else {
            return;
        }
    } else {
        // Keyboard navigation and content changes forget the pending row click.
        mouse_row.reset();
    }
    if( act == "ANY_INPUT" ) {
        // The page binds no zone action; its key comes from the zone screen's own context.
        act = zones_ctxt.input_to_action( ctxt.get_raw_input() );
        if( act == "ERROR" ) {
            // debug_submap_grid lives in DEFAULTMODE instead of the zone context.
            act = debug_ctxt.input_to_action( ctxt.get_raw_input() );
        }
    }
    if( act == "debug_submap_grid" ) {
        g->debug_submap_grid_overlay = !g->debug_submap_grid_overlay;
        return;
    }
    if( act == "SHOW_ALL_ZONES" ) {
        show_all = !show_all;
        return;
    }
    if( act == "TOGGLE_ZONE_OVERLAY" ) {
        g->show_zone_overlay = !g->show_zone_overlay;
        return;
    }
    if( act == "ADD_ZONE" ) {
        add_zone( page );
        return;
    }
    if( zones.empty() ) {
        return;
    }
    auto &mgr = zone_manager::get_manager();
    if( act == "UP" ) {
        active_index--;
        if( active_index < 0 ) {
            active_index = static_cast<int>( zones.size() ) - 1;
        }
    } else if( act == "DOWN" ) {
        active_index++;
        if( active_index >= static_cast<int>( zones.size() ) ) {
            active_index = 0;
        }
    } else if( act == "REMOVE_ZONE" ) {
        mgr.remove( zones[active_index].get() );
        dirty = true;
    } else if( act == "ENABLE_ZONE" ) {
        zones[active_index].get().set_enabled( true );
        dirty = true;
    } else if( act == "DISABLE_ZONE" ) {
        zones[active_index].get().set_enabled( false );
        dirty = true;
    } else if( act == "MOVE_ZONE_UP" && zones.size() > 1 ) {
        if( active_index < static_cast<int>( zones.size() ) - 1 ) {
            mgr.swap( zones[active_index], zones[active_index + 1] );
            active_index++;
            dirty = true;
        }
    } else if( act == "MOVE_ZONE_DOWN" && zones.size() > 1 ) {
        if( active_index > 0 ) {
            mgr.swap( zones[active_index], zones[active_index - 1] );
            active_index--;
            dirty = true;
        }
    } else if( act == "SHOW_ZONE_ON_MAP" ) {
        const zone_data &zone = zones[active_index].get();
        // display_zones indexes the manager's full list, not this tab's filtered list.
        int full_index = active_index;
        const std::vector<zone_manager::ref_zone_data> all = mgr.get_zones();
        for( size_t i = 0; i < all.size(); ++i ) {
            if( &all[i].get() == &zone ) {
                full_index = static_cast<int>( i );
                break;
            }
        }
        const tripoint_abs_omt player_overmap_position = get_avatar().abs_omt_pos();
        const tripoint_abs_omt zone_overmap( project_to<coords::omt>( zone.get_center_point() ) );
        ui::omap::display_zones( player_overmap_position, zone_overmap, full_index );
    } else if( act == "CONFIRM" ) {
        edit_selected( page );
    }
}

void zones_panel::close()
{
    // The tile overlays follow the standalone manager's flag, so clear it on the way out.
    g->set_zones_manager_open( false );
    if( !dirty ) {
        return;
    }
    auto &mgr = zone_manager::get_manager();
    if( query_yn( _( "Save changes?" ) ) ) {
        mgr.save_zones();
    } else {
        mgr.load_zones();
    }
    // Rebuild the cached zone sets so loot sorting and marking see this result immediately.
    mgr.cache_data();
    dirty = false;
}

} // namespace

auto world_hub::zones_screen() -> panel_ptr
{
    return std::make_unique<zones_panel>();
}
