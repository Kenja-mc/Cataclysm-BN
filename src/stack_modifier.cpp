#include "stack_modifier.h"

#include <algorithm>
#include <cstdint>
#include <iterator>

#include "generic_factory.h"
#include "item.h"
#include "json.h"
#include "rng.h"
#include "string_formatter.h"
#include "type_id_implement.h"

namespace
{

generic_factory<stack_modifier> all_stack_modifiers( "stack modifiers" );

} // namespace

IMPLEMENT_STRING_ID( stack_modifier, all_stack_modifiers );

namespace
{

constexpr auto var_prefix = "stack_mod:";

auto var_name( const stack_modifier_id &mod ) -> std::string { return var_prefix + mod.str(); }

auto transferred_count( const int count, const int qty, const int total ) -> int
{
    if( count <= 0 || qty <= 0 ) {
        return 0;
    }
    if( qty >= total ) {
        return count;
    }
    const auto product = static_cast<std::int64_t>( count ) * qty;
    auto moved = static_cast<int>( product / total );
    if( product % total > 0 && rng( 0, total - 1 ) < product % total ) {
        moved++;
    }
    const auto hi = std::min( count, qty );
    return std::clamp( moved, std::min( hi, std::max( 0, count - ( total - qty ) ) ), hi );
}

auto consume_counts( item &source, const int qty, const int total ) -> void
{
    auto &vars = source.item_vars();
    for( auto iter = vars.begin(); iter != vars.end(); ) {
        // Advance before the current count is potentially erased.
        const auto current = iter;
        iter = std::next( iter );
        const auto &key = current->first;
        if( !stack_modifiers::is_count_var( key ) ) {
            continue;
        }
        const auto id = stack_modifier_id( key.substr( std::char_traits<char>::length( var_prefix ) ) );
        if( !id.is_valid() ) {
            continue;
        }
        const auto n = std::clamp( vars.get<int>( key, 0 ), 0, total );
        const auto remaining = n - transferred_count( n, qty, total );
        if( remaining > 0 ) {
            vars.set( key, remaining );
        } else {
            vars.erase( current );
        }
    }
}

} // namespace

void stack_modifier::load( const JsonObject &jo, const std::string & )
{
    mandatory( jo, was_loaded, "name", name );
    optional( jo, was_loaded, "damage", damage, 1.0f );
    optional( jo, was_loaded, "armor_penetration", armor_penetration, 1.0f );
    optional( jo, was_loaded, "dispersion", dispersion, 1.0f );
    optional( jo, was_loaded, "recoil", recoil, 1.0f );
    optional( jo, was_loaded, "price", price, 1.0f );
    optional( jo, was_loaded, "price_postapoc", price_postapoc, 1.0f );
    optional( jo, was_loaded, "ammo_effects", ammo_effects );
    optional( jo, was_loaded, "remove_ammo_effects", remove_ammo_effects );
}

auto stack_modifier::apply_ammo_effects( std::set<ammo_effect_str_id> &effects ) const -> void
{
    for( const auto &effect : remove_ammo_effects ) {
        effects.erase( effect );
    }
    effects.insert( ammo_effects.begin(), ammo_effects.end() );
}

namespace stack_modifiers
{

void load( const JsonObject &jo, const std::string &src ) { all_stack_modifiers.load( jo, src ); }

void reset() { all_stack_modifiers.reset(); }

void check_consistency() { all_stack_modifiers.check(); }

auto count( const item &it, const stack_modifier_id &mod ) -> int { return it.get_var( var_name( mod ), 0 ); }

auto set_count( item &it, const stack_modifier_id &mod, const int n ) -> void
{
    if( n > 0 ) {
    it.set_var( var_name( mod ), n );
    } else {
        it.erase_var( var_name( mod ) );
    }
}

auto on( const item &it ) -> std::vector<stack_modifier_count>
{
    auto result = std::vector<stack_modifier_count>();
    for( const auto &[key, value] : it.item_vars() ) {
        if( is_count_var( key ) ) {
            const auto id = stack_modifier_id( key.substr( std::string( var_prefix ).size() ) );
            if( const auto n = count( it, id ); n > 0 && id.is_valid() ) {
                result.push_back( { .id = id, .count = n } );
            }
        }
    }
    return result;
}

auto is_count_var( const std::string &key ) -> bool { return key.starts_with( var_prefix ); }

auto merge( item &into, const item &from ) -> void
{
for( const auto &m : on( from ) ) {
    set_count( into, m.id, count( into, m.id ) + m.count );
    }
}

auto transfer( item &from, item &to, const int qty ) -> void
{
    if( from.charges > 0 ) {
    clamp( from, from.charges );
    }
    const auto total = std::max( from.charges, 1 );
for( const auto &m : on( from ) ) {
        // Proportional share, with the remainder rounded at random so small splits stay fair.
        const auto moved = transferred_count( m.count, qty, total );
        set_count( from, m.id, m.count - moved );
        set_count( to, m.id, count( to, m.id ) + moved );
    }
}

auto split( item &from, item &part, const int qty ) -> void
{
for( const auto &m : on( part ) ) {
    set_count( part, m.id, 0 );
    }
    transfer( from, part, qty );
}

auto clamp( item &it, const int total ) -> void
{
    consume_counts( it, 0, std::max( total, 0 ) );
}

auto consume( item &it, const int qty ) -> void
{
    const auto total = std::max( it.charges, 0 );
    if( total == 0 || qty <= 0 ) {
        return;
    }
    consume_counts( it, qty, total );
}

auto select_one( const item &source, const int total ) -> std::optional<stack_modifier_id>
{
    if( total <= 0 ) {
        return std::nullopt;
    }
    auto roll = rng( 1, total );
    for( const auto &[key, value] : source.item_vars() ) {
        if( !is_count_var( key ) ) {
            continue;
        }
        const auto id = stack_modifier_id( key.substr( std::char_traits<char>::length( var_prefix ) ) );
        if( !id.is_valid() ) {
            continue;
        }
        const auto n = std::clamp( source.item_vars().get<int>( key, 0 ), 0, total );
        if( roll <= n ) {
            return id;
        }
        roll -= n;
    }
    return std::nullopt;
}

auto consume_selected( item &source, const int qty,
                       const std::optional<stack_modifier_id> &selected ) -> void
{
    if( qty <= 0 || source.charges <= 0 ) {
        return;
    }
    clamp( source, source.charges );
    if( selected ) {
        set_count( source, *selected, count( source, *selected ) - 1 );
    }
    const auto total = source.charges - 1;
    if( total > 0 && qty > 1 ) {
        consume_counts( source, qty - 1, total );
    }
}

auto price_multiplier( const item &it, const int total, const bool practical ) -> float
{
    if( total <= 0 ) {
        return 1.0f;
    }
    auto result = 1.0f;
    for( const auto &[key, value] : it.item_vars() ) {
        if( !is_count_var( key ) ) {
            continue;
        }
        const auto id = stack_modifier_id( key.substr( std::char_traits<char>::length( var_prefix ) ) );
        if( !id.is_valid() ) {
            continue;
        }
        const auto n = std::clamp( it.item_vars().get<int>( key, 0 ), 0, total );
        const auto multiplier = practical ? id->price_postapoc : id->price;
        result += static_cast<float>( n ) / total * ( multiplier - 1.0f );
    }
    return result;
}

auto ammo_effect_count( const item &source, const ammo_effect_str_id &effect,
                        const bool base_has_effect ) -> int
{
    const auto total = std::max( source.charges, 1 );
    auto result = base_has_effect ? total : 0;
    for( const auto &[key, value] : source.item_vars() ) {
        if( !is_count_var( key ) ) {
            continue;
        }
        const auto id = stack_modifier_id( key.substr( std::char_traits<char>::length( var_prefix ) ) );
        if( !id.is_valid() ) {
            continue;
        }
        const auto has_effect = id->ammo_effects.contains( effect ) ||
                                ( base_has_effect && !id->remove_ammo_effects.contains( effect ) );
        if( has_effect != base_has_effect ) {
            const auto n = std::clamp( source.item_vars().get<int>( key, 0 ), 0, total );
            result += has_effect ? n : -n;
        }
    }
    return std::clamp( result, 0, total );
}

auto describe( const item &it ) -> std::string
{
    auto out = std::string();
    for( const auto &m : on( it ) ) {
        const auto n = it.count_by_charges() ? std::min( m.count, std::max( it.charges, 1 ) ) : m.count;
        out += string_format( ", %d %s", n, m.id->name.translated() );
    }
    return out;
}

} // namespace stack_modifiers
