#include "item_variant.h"

#include <algorithm>
#include <numeric>

#include "debug.h"
#include "generic_factory.h"
#include "item.h"
#include "itype.h"
#include "json.h"
#include "rng.h"
#include "type_id_implement.h"

namespace
{

generic_factory<item_variant_set> all_variant_sets( "item variants" );

} // namespace

IMPLEMENT_STRING_ID( item_variant_set, all_variant_sets );

namespace
{

constexpr auto var_name = "variant";

auto set_for( const item &it ) -> const item_variant_set * // *NOPAD*
{
    const auto id = string_id<item_variant_set>( it.typeId().str() );
    return id.is_valid() ? &id.obj() : nullptr;
}

} // namespace

void item_variant_set::load( const JsonObject &jo, const std::string & )
{
    optional( jo, was_loaded, "cosmetic", cosmetic, false );
    variants.clear();
    for( JsonObject v : jo.get_array( "variants" ) ) {
        auto variant = item_variant{ .name = translation( translation::plural_tag() ) };
        v.read( "id", variant.id, true );
        v.read( "name", variant.name, true );
        v.read( "description", variant.description );
        v.read( "weight", variant.weight );
        v.read( "price_multiplier", variant.price_multiplier );
        v.read( "looks_like", variant.looks_like );
        v.read( "material", variant.materials );
        for( JsonArray c : v.get_array( "components" ) ) {
            variant.components.push_back( { .id = itype_id( c.get_string( 0 ) ), .count = c.get_int( 1 ) } );
        }
        variants.push_back( std::move( variant ) );
    }
}

void item_variant_set::check() const
{
    if( !itype_id( id.str() ).is_valid() ) {
        debugmsg( "item_variants %s does not match an item type", id.str() );
    }
    for( const auto &v : variants ) {
        for( const auto &m : v.materials ) {
            if( !m.is_valid() ) {
                debugmsg( "item_variants %s: variant %s has unknown material %s", id.str(), v.id, m.str() );
            }
        }
        for( const auto &c : v.components ) {
            if( !c.id.is_valid() ) {
                debugmsg( "item_variants %s: variant %s yields unknown item %s", id.str(), v.id, c.id.str() );
            }
        }
    }
}

namespace item_variants
{

void load( const JsonObject &jo, const std::string &src ) { all_variant_sets.load( jo, src ); }

void reset() { all_variant_sets.reset(); }

void check_consistency() { all_variant_sets.check(); }

auto assign_random( item &it ) -> void
{
    const auto *set = set_for( it );
    if( set == nullptr || set->variants.empty() || it.has_var( var_name ) ) {
        return;
    }
    const auto total = std::accumulate( set->variants.begin(), set->variants.end(), 0,
    []( const int sum, const item_variant & v ) { return sum + v.weight; } );
    auto roll = rng( 1, std::max( total, 1 ) );
    for( const auto &v : set->variants ) {
        roll -= v.weight;
        if( roll <= 0 ) {
            it.set_var( var_name, v.id );
            return;
        }
    }
}

auto set( item &it, const std::string &variant ) -> void { it.set_var( var_name, variant ); }

auto of( const item &it ) -> const item_variant * // *NOPAD*
{
    if( !it.has_var( var_name ) ) {
        return nullptr;
    }
    const auto *set = set_for( it );
    if( set == nullptr ) {
        return nullptr;
    }
    const auto chosen = it.get_var( var_name, std::string() );
    for( const auto &v : set->variants ) {
        if( v.id == chosen ) {
            return &v;
        }
    }
    return nullptr;
}

auto cosmetic( const itype &type ) -> bool
{
    const auto id = string_id<item_variant_set>( type.get_id().str() );
    return id.is_valid() && id->cosmetic;
}

auto sprite( const item &it ) -> std::string
{
    const auto *variant = of( it );
    return variant == nullptr ? std::string() : variant->looks_like.empty() ? variant->id : variant->looks_like;
}

auto find( const itype_id &type, const std::string &variant ) -> const item_variant * // *NOPAD*
{
    const auto id = string_id<item_variant_set>( type.str() );
    if( !id.is_valid() ) {
        return nullptr;
    }
    const auto found = std::ranges::find( id->variants, variant, &item_variant::id );
    return found != id->variants.end() ? &*found : nullptr;
}

auto disassembly_extras( const item &it ) -> std::vector<variant_component>
{
    const auto *variant = of( it );
    return variant != nullptr ? variant->components : std::vector<variant_component>();
}

} // namespace item_variants
