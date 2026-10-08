#include "stack_modifier.h"

#include <algorithm>

#include "generic_factory.h"
#include "item.h"
#include "json.h"
#include "rng.h"
#include "string_formatter.h"
#include "type_id_implement.h"

namespace
{

generic_factory<stack_modifier> all_stack_modifiers( "stack modifiers" );

constexpr auto var_prefix = "stack_mod:";

auto var_name( const stack_modifier_id &mod ) -> std::string { return var_prefix + mod.str(); }

} // namespace

IMPLEMENT_STRING_ID( stack_modifier, all_stack_modifiers );

void stack_modifier::load( const JsonObject &jo, const std::string & )
{
    mandatory( jo, was_loaded, "name", name );
    optional( jo, was_loaded, "damage", damage, 1.0f );
    optional( jo, was_loaded, "armor_penetration", armor_penetration, 1.0f );
    optional( jo, was_loaded, "dispersion", dispersion, 1.0f );
    optional( jo, was_loaded, "recoil", recoil, 1.0f );
    optional( jo, was_loaded, "blocks_disassembly", blocks_disassembly, false );
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
        auto moved = m.count * qty / total;
        if( rng( 0, total - 1 ) < m.count * qty % total ) {
            moved++;
        }
        // Units left behind cannot outnumber the charges left behind.
        moved = std::clamp( moved, std::max( 0, m.count - ( total - qty ) ), std::min( m.count, qty ) );
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
    for( const auto &m : on( it ) ) {
        set_count( it, m.id, std::min( m.count, total ) );
    }
}

auto take_one( item &source, const int total ) -> std::optional<stack_modifier_id>
{
    if( total <= 0 ) {
        return std::nullopt;
    }
    auto roll = rng( 1, total );
    for( const auto &m : on( source ) ) {
        if( roll <= m.count ) {
            set_count( source, m.id, m.count - 1 );
            return m.id;
        }
        roll -= m.count;
    }
    return std::nullopt;
}

auto describe( const item &it ) -> std::string
{
    auto out = std::string();
    for( const auto &m : on( it ) ) {
        out += string_format( ", %d %s", m.count, m.id->name.translated() );
    }
    return out;
}

} // namespace stack_modifiers
