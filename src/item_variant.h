#pragma once

#include <optional>
#include <string>
#include <vector>

#include "color.h"
#include "string_id.h"
#include "translations.h"
#include "type_id.h"

class item;
struct itype;
class JsonObject;
struct item_variant_set;

struct variant_component {
    itype_id id;
    int count = 0;
};

struct item_variant {
    std::string id;
    translation name;
    translation description;
    int weight = 1;
    float price_multiplier = 1.0f;
    std::optional<nc_color> color;
    std::string looks_like;
    std::vector<material_id> materials;
    std::vector<variant_component> components;
};

struct item_variant_set {
    string_id<item_variant_set> id;
    bool was_loaded = false;

    std::vector<item_variant> variants;
    bool cosmetic = false;

    auto load( const JsonObject &jo, const std::string &src ) -> void;
    auto check() const -> void;
};

namespace item_variants
{

auto load( const JsonObject &jo, const std::string &src ) -> void;
auto reset() -> void;
auto check_consistency() -> void;

auto assign_random( item &it ) -> void;
auto set( item &it, const std::string &variant ) -> void;
auto of( const item &it ) -> const item_variant *; // *NOPAD*
auto cosmetic( const itype &type ) -> bool;
auto sprite( const item &it ) -> std::string;
auto find( const itype_id &type, const std::string &variant ) -> const item_variant *; // *NOPAD*

auto disassembly_extras( const item &it ) -> std::vector<variant_component>;

}
