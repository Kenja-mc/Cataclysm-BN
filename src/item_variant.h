#pragma once

#include <string>
#include <vector>

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

/// One look of an item type, e.g. the gold and ruby version of a ring.
struct item_variant {
    std::string id;
    translation name;
    translation description;
    int weight = 1;
    /** Relative to the item type's price, e.g. diamonds are worth more than garnets. */
    float price_multiplier = 1.0f;
    /// Sprite to look for in tilesets; defaults to the variant id.
    std::string looks_like;
    /// Replaces the item type's materials when set.
    std::vector<material_id> materials;
    /// Disassembly yields these on top of the item type's own recipe, e.g. the metal and the gem.
    std::vector<variant_component> components;
};

/// Variants of a single item type. Items of that type pick one when created and remember it, so a
/// family of near-identical items (gem jewelry and the like) can share one item type.
struct item_variant_set {
    string_id<item_variant_set> id;
    bool was_loaded = false;

    std::vector<item_variant> variants;
    /// Variants only change looks, name and value, so items of different variants stack together.
    bool cosmetic = false;

    void load( const JsonObject &jo, const std::string &src );
    void check() const;
};

namespace item_variants
{

void load( const JsonObject &jo, const std::string &src );
void reset();
void check_consistency();

/// Picks a variant for a freshly created item of a type that has variants.
auto assign_random( item &it ) -> void;
/// Forces a specific variant, e.g. when migrating an old item id.
auto set( item &it, const std::string &variant ) -> void;
auto of( const item &it ) -> const item_variant *; // *NOPAD*
auto cosmetic( const itype &type ) -> bool;
/// Sprite id for the item's variant, or empty when it has none.
auto sprite( const item &it ) -> std::string;
auto find( const itype_id &type, const std::string &variant ) -> const item_variant *; // *NOPAD*

/// Extra disassembly results the variant contributes (the metal and gem of a ring).
auto disassembly_extras( const item &it ) -> std::vector<variant_component>;

} // namespace item_variants
