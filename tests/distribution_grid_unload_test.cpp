#include "../src/map/map.h"
#include "../src/overmap/overmap.h"
#include "../src/overmap/overmapbuffer.h"
#include "active_tile_data.h"
#include "active_tile_data_def.h"
#include "calendar.h"
#include "catch/catch.hpp"
#include "coordinates.h"
#include "debug.h"
#include "distribution_grid.h"
#include "game.h"
#include "item.h"
#include "map/mapbuffer.h"
#include "map_helpers.h"
#include "state_helpers.h"
#include "type_id.h"
#include "units_angle.h"
#include "vehicle/vehicle.h"
#include "vehicle/vehicle_part.h"

#include <algorithm>
#include <string>
#include <utility>

namespace {

const auto f_battery = furn_str_id("f_battery");
const auto f_cable_connector = furn_str_id("f_cable_connector");

auto clear_grid_connections(const tripoint_abs_omt& omt_pos) -> void {
    auto om = ACTIVE_OVERMAP_BUFFER.get_om_global(omt_pos);
    om.om->set_electric_grid_connections(om.local, {});
}

auto install_grid_cable(vehicle& veh, const tripoint_abs_ms& target) -> bool {
    const tripoint_mnt_veh cable_part_pos;
    vehicle_part cable(vpart_id("jumper_cable"), cable_part_pos, item::spawn("jumper_cable"), &veh);
    cable.target.first = target;
    cable.target.second = target;
    cable.set_flag(vehicle_part::targets_grid);
    return veh.install_part(cable_part_pos, std::move(cable)) >= 0;
}

}

TEST_CASE("vehicle_power_ignores_grid_on_unloaded_submap", "[map][vehicle][grid]") {
    clear_all_state();
    move_player_out_of_the_way();

    auto& tracker = get_distribution_grid_tracker();
    const auto dim = tracker.get_dimension_id();
    const tripoint_abs_sm grid_sm(136, 250, 0);
    const auto grid_omt = project_to<coords::omt>(grid_sm);
    clear_grid_connections(grid_omt);

    const auto connector_local = tripoint_bub_ms(13, 10, 0);
    tripoint_abs_ms connector_abs;
    {
        map far_map(2);
        far_map.load(grid_sm.xy(), false);
        far_map.furn_set(connector_local, f_cable_connector);
        far_map.furn_set(tripoint_bub_ms(14, 10, 0), f_battery);
        connector_abs = map_local_to_abs(far_map, connector_local);
    }
    REQUIRE(active_tiles::furn_at<vehicle_connector_tile>(connector_abs) != nullptr);

    tracker.on_submap_loaded(grid_sm, dim);
    REQUIRE(tracker.debug_grid_id(grid_omt) != 0);
    REQUIRE(!tracker.grid_at(connector_abs).empty());

    auto* veh =
        get_map().add_vehicle(vproto_id("car"), tripoint_bub_ms(60, 60, 0), 0_degrees, 0, 0, false);
    REQUIRE(veh != nullptr);
    REQUIRE(install_grid_cable(*veh, connector_abs));
    REQUIRE(std::ranges::any_of(veh->loose_parts, [&](const int part) {
        return veh->cpart(part).has_flag(vehicle_part::targets_grid);
    }));

    tracker.on_submap_unloaded(grid_sm, dim);
    CHECK(tracker.debug_grid_id(grid_omt) == 0);

    MAPBUFFER.unload_omt(grid_omt, false);
    REQUIRE(tracker.grid_at(connector_abs).empty());

    auto deficit = 0;
    const auto dmsg = capture_debugmsg_during([&]() {
        deficit = veh->discharge_battery(10, true);
        tracker.update(calendar::turn);
    });
    CHECK(deficit == 10);
    CHECK(dmsg.empty());
}
