#pragma once

#include <optional>
#include <set>
#include <string>
#include <vector>

#include "string_id.h"
#include "translations.h"
#include "type_id.h"

class item;
class JsonObject;
struct stack_modifier;

using stack_modifier_id = string_id<stack_modifier>;

struct stack_modifier {
    stack_modifier_id id;
    bool was_loaded = false;

    translation name;
    float damage = 1.0f;
    float armor_penetration = 1.0f;
    float dispersion = 1.0f;
    float recoil = 1.0f;
    float price = 1.0f;
    float price_postapoc = 1.0f;
    std::set<ammo_effect_str_id> ammo_effects;
    std::set<ammo_effect_str_id> remove_ammo_effects;

    void load( const JsonObject &jo, const std::string &src );
    void check() const {}
    auto apply_ammo_effects( std::set<ammo_effect_str_id> &effects ) const -> void;
};

struct stack_modifier_count {
    stack_modifier_id id;
    int count = 0;
};

namespace stack_modifiers
{

void load( const JsonObject &jo, const std::string &src );
void reset();
void check_consistency();

auto count( const item &it, const stack_modifier_id &mod ) -> int;
auto set_count( item &it, const stack_modifier_id &mod, int n ) -> void;
auto on( const item &it ) -> std::vector<stack_modifier_count>;
auto is_count_var( const std::string &key ) -> bool;

auto merge( item &into, const item &from ) -> void;
auto transfer( item &from, item &to, int qty ) -> void;
auto split( item &from, item &part, int qty ) -> void;
auto clamp( item &it, int total ) -> void;
auto consume( item &it, int qty ) -> void;
auto select_one( const item &source, int total ) -> std::optional<stack_modifier_id>;
auto consume_selected( item &source, int qty,
                       const std::optional<stack_modifier_id> &selected ) -> void;
auto price_multiplier( const item &it, int total, bool practical ) -> float;
auto ammo_effect_count( const item &source, const ammo_effect_str_id &effect,
                        bool base_has_effect ) -> int;
auto describe( const item &it ) -> std::string;

}
