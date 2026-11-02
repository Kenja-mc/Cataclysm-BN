#pragma once

#include <optional>

#include "action.h"
#include "coordinates.h"

class avatar;
class input_context;
class map;

namespace aim_reticle
{

enum class attack_mode {
    direct,
    fire_command
};

struct attack_options {
    attack_mode mode = attack_mode::fire_command;
    bool force_melee = false;
};

auto enabled() -> bool;

auto active() -> bool;

auto pos() -> std::optional<tripoint_bub_ms>;

auto select( avatar &you, map &m, const tripoint_bub_ms &p ) -> bool;

auto cycle( avatar &you, map &m, bool reverse = false ) -> bool;

auto arrow_move( const action_id act, input_context &ctxt ) -> bool;

auto move( avatar &you, map &m, const point_rel_ms &delta ) -> void;

auto attack( avatar &you, map &m, const attack_options &opts ) -> std::optional<action_id>;

auto clear() -> bool;

}
