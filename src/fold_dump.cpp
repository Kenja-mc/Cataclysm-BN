#include "fold_dump.h"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include "calendar.h"
#include "damage.h"
#include "init.h"
#include "item.h"
#include "item_factory.h"
#include "itype.h"
#include "json.h"
#include "mod_manager.h"
#include "recipe.h"
#include "recipe_dictionary.h"
#include "requirements.h"
#include "units.h"

#if __has_include("item_variant.h")
#  include "item_variant.h"
#  define FOLD_DUMP_VARIANTS 1
#endif
#if __has_include("stack_modifier.h")
#  include "stack_modifier.h"
#  define FOLD_DUMP_STACK_MODIFIERS 1
#endif

namespace
{

struct spawn_request {
    itype_id id;
    bool has_charges = false;
    int charges = 0;
    std::string save_json;
};

auto to_ml( const units::volume v ) -> double
{
    return static_cast<double>( units::to_milliliter( v ) );
}

auto to_g( const units::mass m ) -> double
{
    return static_cast<double>( units::to_gram( m ) );
}

template<typename Container>
void write_ids( JsonOut &js, const std::string &name, const Container &values )
{
    js.member( name );
    js.start_array();
    for( const auto &v : values ) {
        js.write( v );
    }
    js.end_array();
}

void write_damage( JsonOut &js, const damage_instance &damage, const float damage_mult,
                   const float penetration_mult )
{
    js.start_array();
    for( const damage_unit &du : damage.damage_units ) {
        js.start_object();
        js.member( "type" );
        js.write( static_cast<int>( du.type ) );
        js.member( "amount" );
        js.write( du.amount * damage_mult );
        js.member( "res_pen" );
        js.write( du.res_pen * penetration_mult );
        js.member( "res_mult" );
        js.write( du.res_mult );
        js.member( "damage_multiplier" );
        js.write( du.damage_multiplier );
        js.end_object();
    }
    js.end_array();
}

void write_variant( JsonOut &js, const item &obj )
{
    std::string variant;
#ifdef FOLD_DUMP_VARIANTS
    variant = obj.get_var( "variant", std::string() );
#else
    ( void )obj;
#endif
    js.member( "variant", variant );
}

void write_stack_modifiers( JsonOut &js, const item &obj )
{
    js.member( "stack_modifiers" );
    js.start_object();
#ifdef FOLD_DUMP_STACK_MODIFIERS
    for( const stack_modifier_count &m : stack_modifiers::on( obj ) ) {
        js.member( m.id.str() );
        js.write( m.count );
    }
#else
    ( void )obj;
#endif
    js.end_object();
}

auto modifier_product( const item &obj, const std::string &what ) -> float
{
    float result = 1.0f;
#ifdef FOLD_DUMP_STACK_MODIFIERS
    for( const stack_modifier_count &m : stack_modifiers::on( obj ) ) {
        if( what == "damage" ) {
            result *= m.id->damage;
        } else if( what == "armor_penetration" ) {
            result *= m.id->armor_penetration;
        } else if( what == "dispersion" ) {
            result *= m.id->dispersion;
        } else if( what == "recoil" ) {
            result *= m.id->recoil;
        }
    }
#else
    ( void )obj;
    ( void )what;
#endif
    return result;
}

void write_effective_modifier( JsonOut &js, const item &obj )
{
    js.member( "effective_modifier" );
    js.start_object();
    js.member( "damage", modifier_product( obj, "damage" ) );
    js.member( "armor_penetration", modifier_product( obj, "armor_penetration" ) );
    js.member( "dispersion", modifier_product( obj, "dispersion" ) );
    js.member( "recoil", modifier_product( obj, "recoil" ) );
    js.end_object();
}

auto variant_price_multiplier( const item &obj ) -> float
{
#ifdef FOLD_DUMP_VARIANTS
    if( const item_variant *v = item_variants::of( obj ) ) {
        return v->price_multiplier;
    }
#else
    ( void )obj;
#endif
    return 1.0f;
}

void write_contents( JsonOut &js, const item &obj )
{
    js.member( "contents" );
    js.start_array();
    for( const item *child : obj.contents.all_items_top() ) {
        js.start_object();
        js.member( "type_id", child->typeId().str() );
        js.member( "charges", child->charges );
        js.member( "ammo_current", child->ammo_current().str() );
        js.member( "ammo_remaining", child->ammo_remaining() );
        write_variant( js, *child );
        write_stack_modifiers( js, *child );
        js.end_object();
    }
    js.end_array();
}

void write_comestible( JsonOut &js, const item &obj )
{
    js.member( "comestible" );
    if( !obj.type->comestible ) {
        js.write_null();
        return;
    }
    const islot_comestible &c = *obj.type->comestible;
    js.start_object();
    js.member( "comesttype", c.comesttype );
    js.member( "tool", c.tool.str() );
    js.member( "def_charges", c.def_charges );
    js.member( "quench", c.quench );
    js.member( "kcal", c.default_nutrition.kcal );
    js.member( "vitamins" );
    js.start_object();
    for( const auto &[vit, amount] : c.default_nutrition.vitamins ) {
        js.member( vit.str() );
        js.write( amount );
    }
    js.end_object();
    js.member( "healthy", c.healthy );
    js.member( "fun", obj.get_comestible_fun() );
    js.member( "addict", c.addict );
    js.member( "stim", c.stim );
    js.member( "fatigue_mod", c.fatigue_mod );
    js.member( "parasites", c.parasites );
    js.member( "radiation", c.radiation );
    js.member( "spoils_turns", static_cast<int>( to_turns<int>( c.spoils ) ) );
    js.member( "cooks_like", c.cooks_like.str() );
    js.member( "smoking_result", c.smoking_result.str() );
    js.member( "monotony_penalty", c.monotony_penalty );
    js.end_object();
}

void write_book( JsonOut &js, const item &obj )
{
    js.member( "book" );
    if( !obj.type->book ) {
        js.write_null();
        return;
    }
    const islot_book &b = *obj.type->book;
    js.start_object();
    js.member( "skill", b.skill.str() );
    js.member( "martial_art", b.martial_art.str() );
    js.member( "level", b.level );
    js.member( "req", b.req );
    js.member( "fun", b.fun );
    js.member( "intel", b.intel );
    js.member( "time", b.time );
    js.member( "chapters", b.chapters );
    js.member( "recipes" );
    js.start_array();
    for( const book_recipe &r : b.recipes ) {
        js.start_object();
        js.member( "recipe", r.recipe->ident().str() );
        js.member( "skill_level", r.skill_level );
        js.end_object();
    }
    js.end_array();
    js.end_object();
}

void write_ammo( JsonOut &js, const item &obj )
{
    js.member( "ammo" );
    if( !obj.type->ammo ) {
        js.write_null();
        return;
    }
    const islot_ammo &a = *obj.type->ammo;
    const float damage_mult = modifier_product( obj, "damage" );
    const float penetration_mult = modifier_product( obj, "armor_penetration" );
    const float dispersion_mult = modifier_product( obj, "dispersion" );
    const float recoil_mult = modifier_product( obj, "recoil" );
    std::set<ammo_effect_str_id> effects = a.ammo_effects;
#ifdef FOLD_DUMP_STACK_MODIFIERS
    // Firing applies the selected modifier to gun.ammo_effects() just before the shot; the
    // comparison items are pure migrated stacks, so the whole-stack effective set is this one.
    for( const stack_modifier_count &m : stack_modifiers::on( obj ) ) {
        m.id->apply_ammo_effects( effects );
    }
#endif
    js.start_object();
    js.member( "ammo_type", a.type.str() );
    js.member( "damage" );
    write_damage( js, a.damage, damage_mult, penetration_mult );
    js.member( "range", a.range );
    js.member( "dispersion", static_cast<double>( a.dispersion ) * dispersion_mult );
    js.member( "recoil", static_cast<double>( a.recoil ) * recoil_mult );
    js.member( "loudness", a.loudness );
    js.member( "speed", a.speed );
    js.member( "def_charges", a.def_charges );
    write_ids( js, "effects", effects );
    js.member( "casing", a.casing ? a.casing->str() : std::string() );
    js.member( "drop", a.drop.str() );
    js.member( "drop_count", a.drop_count );
    js.end_object();
}

void write_magazine( JsonOut &js, const item &obj )
{
    js.member( "magazine" );
    if( !obj.type->magazine ) {
        js.write_null();
        return;
    }
    const islot_magazine &m = *obj.type->magazine;
    js.start_object();
    write_ids( js, "type", m.type );
    js.member( "capacity", m.capacity );
    js.member( "count", m.count );
    js.member( "default_ammo", m.default_ammo.str() );
    js.member( "reliability", m.reliability );
    js.member( "reload_time", m.reload_time );
    js.member( "linkage", m.linkage ? m.linkage->str() : std::string() );
    js.member( "protects_contents", m.protects_contents );
    js.end_object();
}

void write_gun( JsonOut &js, const item &obj )
{
    js.member( "gun" );
    if( !obj.type->gun ) {
        js.write_null();
        return;
    }
    const islot_gun &g = *obj.type->gun;
    js.start_object();
    js.member( "skill_used", g.skill_used.str() );
    write_ids( js, "ammo", g.ammo );
    js.member( "clip", g.clip );
    js.member( "reload_time", g.reload_time );
    js.member( "durability", g.durability );
    js.member( "sight_dispersion", g.sight_dispersion );
    js.member( "loudness", g.loudness );
    js.member( "speed", g.speed );
    js.member( "ups_charges", g.ups_charges );
    js.member( "damage" );
    write_damage( js, g.damage, 1.0f, 1.0f );
    js.member( "range", g.range );
    js.member( "dispersion", g.dispersion );
    js.member( "recoil", g.recoil );
    js.member( "ammo_to_fire", g.ammo_to_fire );
    write_ids( js, "built_in_mods", g.built_in_mods );
    write_ids( js, "default_mods", g.default_mods );
    js.end_object();
}

void write_tool( JsonOut &js, const item &obj )
{
    js.member( "tool" );
    if( !obj.type->tool ) {
        js.write_null();
        return;
    }
    const islot_tool &t = *obj.type->tool;
    js.start_object();
    write_ids( js, "ammo_id", t.ammo_id );
    js.member( "max_charges", t.max_charges );
    js.member( "def_charges", t.def_charges );
    js.member( "charge_factor", t.charge_factor );
    js.member( "charges_per_use", t.charges_per_use );
    js.member( "turns_per_charge", t.turns_per_charge );
    js.member( "power_draw", t.power_draw );
    js.member( "subtype", t.subtype.str() );
    js.member( "revert_to", t.revert_to ? t.revert_to->str() : std::string() );
    js.member( "rand_charges" );
    js.start_array();
    for( const int charge : t.rand_charges ) {
        js.write( charge );
    }
    js.end_array();
    js.end_object();
}

void write_container( JsonOut &js, const item &obj )
{
    js.member( "container" );
    if( !obj.type->container ) {
        js.write_null();
        return;
    }
    const islot_container &c = *obj.type->container;
    js.start_object();
    js.member( "contains_ml", to_ml( c.contains ) );
    js.member( "seals", c.seals );
    js.member( "watertight", c.watertight );
    js.member( "preserves", c.preserves );
    js.member( "unseals_into", c.unseals_into.str() );
    js.end_object();
}

void write_battery( JsonOut &js, const item &obj )
{
    js.member( "battery" );
    if( !obj.type->battery ) {
        js.write_null();
        return;
    }
    js.start_object();
    js.member( "max_capacity_j",
               static_cast<double>( units::to_joule( obj.type->battery->max_capacity ) ) );
    js.end_object();
}

void write_armor( JsonOut &js, const item &obj )
{
    js.member( "armor" );
    if( !obj.type->armor ) {
        js.write_null();
        return;
    }
    const islot_armor &a = *obj.type->armor;
    js.start_object();
    js.member( "thickness", a.thickness );
    js.member( "warmth", a.warmth );
    js.member( "env_resist", a.env_resist );
    js.member( "env_resist_w_filter", a.env_resist_w_filter );
    js.member( "storage_ml", to_ml( a.storage ) );
    js.member( "hearing_protection", a.hearing_protection );
    js.member( "adv_hearing_protection", a.adv_hearing_protection );
    js.member( "portions" );
    js.start_array();
    for( const armor_portion_data &p : a.data ) {
        js.start_object();
        js.member( "encumber", p.encumber );
        js.member( "max_encumber", p.max_encumber );
        js.member( "coverage", p.coverage );
        js.member( "covers" );
        js.start_array();
        for( const bodypart_str_id &bp : p.covers ) {
            js.write( bp.str() );
        }
        js.end_array();
        js.end_object();
    }
    js.end_array();
    js.end_object();
}

void write_uncraft( JsonOut &js, const item &obj )
{
    js.member( "uncraft" );
    const recipe &r = recipe_dictionary::get_uncraft( obj.typeId() );
    if( r.result().is_null() ) {
        js.write_null();
        return;
    }
    js.start_object();
    js.member( "time", r.time );
    js.member( "skill", r.skill_used.str() );
    js.member( "difficulty", r.difficulty );
    js.member( "components" );
    js.start_array();
    for( const item_comp &comp : obj.get_uncraft_components() ) {
        js.start_object();
        js.member( "item", comp.type.str() );
        js.member( "count", comp.count );
        js.end_object();
    }
    js.end_array();
    js.end_object();
}

void write_item_props( JsonOut &js, const item &obj )
{
    js.start_object();
    js.member( "type_id", obj.typeId().str() );
    js.member( "charges", obj.charges );
    js.member( "ammo_remaining", obj.ammo_remaining() );
    js.member( "ammo_capacity", obj.ammo_capacity() );
    js.member( "ammo_capacity_potential", obj.ammo_capacity( true ) );
    js.member( "ammo_current", obj.ammo_current().str() );
    write_ids( js, "ammo_types", obj.ammo_types() );
    js.member( "ammo_default", obj.ammo_default().str() );
    js.member( "magazine_integral", obj.magazine_integral() );
    js.member( "magazine_default", obj.magazine_default().str() );
    write_ids( js, "magazine_compatible", obj.magazine_compatible() );
    js.member( "count_by_charges", obj.count_by_charges() );
    write_variant( js, obj );
    write_stack_modifiers( js, obj );
    write_effective_modifier( js, obj );
    write_contents( js, obj );

    js.member( "weight_grams", to_g( obj.weight() ) );
    js.member( "type_weight_grams", to_g( obj.type->weight ) );
    js.member( "volume_ml", to_ml( obj.volume() ) );
    js.member( "type_volume_ml", to_ml( obj.type->volume ) );
    const float price_mult = variant_price_multiplier( obj );
    float modifier_price = 1.0f;
    float modifier_price_post = 1.0f;
#ifdef FOLD_DUMP_STACK_MODIFIERS
    if( obj.count_by_charges() && obj.charges > 0 ) {
        modifier_price = stack_modifiers::price_multiplier( obj, obj.charges, false );
        modifier_price_post = stack_modifiers::price_multiplier( obj, obj.charges, true );
    }
#endif
    js.member( "type_price_cents",
               static_cast<double>( units::to_cent( obj.type->price ) ) * price_mult * modifier_price );
    js.member( "type_price_post_cents",
               static_cast<double>( units::to_cent( obj.type->price_post ) ) * price_mult *
               modifier_price_post );
    js.member( "price_cents", static_cast<double>( obj.price( false ) ) );
    js.member( "price_post_cents", static_cast<double>( obj.price( true ) ) );

    write_ids( js, "materials", obj.made_of() );
    write_ids( js, "flags", obj.get_flags() );
    js.member( "use_methods" );
    js.start_array();
    for( const auto &entry : obj.type->use_methods ) {
        js.write( entry.first );
    }
    js.end_array();
    js.member( "qualities" );
    js.start_object();
    for( const auto &[quality, level] : obj.type->qualities ) {
        js.member( quality.str() );
        js.write( level );
    }
    js.end_object();

    js.member( "melee_to_hit", obj.type->m_to_hit );
    js.member( "melee_damage" );
    js.start_array();
    for( int i = 0; i < NUM_DT; ++i ) {
        if( obj.type->melee[i] != 0 ) {
            js.start_object();
            js.member( "type" );
            js.write( i );
            js.member( "amount", obj.type->melee[i] );
            js.end_object();
        }
    }
    js.end_array();
    write_ids( js, "techniques", obj.type->techniques );

    js.member( "rigid", obj.type->rigid );
    js.member( "light_emission", obj.type->light_emission );
    js.member( "has_light_color", obj.type->light_color.has_value() );
    js.member( "default_container",
               obj.type->default_container ? obj.type->default_container->str() : std::string() );

    write_comestible( js, obj );
    write_book( js, obj );
    write_ammo( js, obj );
    write_magazine( js, obj );
    write_gun( js, obj );
    write_tool( js, obj );
    write_container( js, obj );
    write_battery( js, obj );
    write_armor( js, obj );
    write_uncraft( js, obj );
    js.end_object();
}

auto serialize_item( const item &obj ) -> std::string
{
    std::ostringstream out;
    JsonOut js( out );
    obj.serialize( js );
    return out.str();
}

auto spawn_with_charges( const itype_id &id, const spawn_request &request ) -> detached_ptr<item>
{
    // Suppress randomized tool charges so the dump is reproducible; rand_charges is compared
    // as type data instead.
    detached_ptr<item> spawned = request.has_charges
                                  ? item::spawn( id, calendar::turn )
                                  : item::spawn( id, calendar::turn, item::default_charges_tag{} );
    if( !spawned ) {
        return spawned;
    }
    item &obj = *spawned;
    if( request.has_charges ) {
        const int ch = request.charges;
        if( obj.count_by_charges() || obj.made_of( LIQUID ) ) {
            obj.charges = std::max( 1, ch );
        } else if( obj.is_tool() ) {
            const int qty = std::min( ch, obj.ammo_capacity() );
            obj.charges = qty;
            if( !obj.ammo_types().empty() && qty > 0 ) {
                obj.ammo_set( obj.ammo_default(), qty );
            }
        } else if( obj.type->can_have_charges() ) {
            obj.charges = ch;
        }
        if( ch > 0 && ( obj.is_gun() || obj.is_magazine() ) ) {
            if( !obj.ammo_types().empty() ) {
                obj.ammo_set( obj.ammo_default(), ch );
            }
            if( obj.ammo_data() && obj.magazine_integral() ) {
                obj.charges = std::min( obj.charges, obj.ammo_capacity() );
            } else {
                obj.charges = 0;
            }
        }
    }
    return spawned;
}

auto read_requests( const std::string &path, std::vector<spawn_request> &requests ) -> bool
{
    std::ifstream in( path );
    if( !in ) {
        std::cerr << "fold dump: cannot open " << path << '\n';
        return false;
    }
    JsonIn jsin( in );
    if( !jsin.test_array() ) {
        std::cerr << "fold dump: input must be a JSON array of {id, charges} requests\n";
        return false;
    }
    jsin.start_array();
    while( !jsin.end_array() ) {
        JsonObject jo = jsin.get_object();
        spawn_request request;
        request.id = itype_id( jo.get_string( "id" ) );
        if( jo.has_int( "charges" ) ) {
            request.has_charges = true;
            request.charges = jo.get_int( "charges" );
        }
        requests.push_back( request );
    }
    return true;
}

auto read_fixture( const std::string &path, std::vector<spawn_request> &requests ) -> bool
{
    std::ifstream in( path );
    if( !in ) {
        std::cerr << "fold dump: cannot open " << path << '\n';
        return false;
    }
    JsonIn jsin( in );
    JsonObject root = jsin.get_object();
    if( !root.has_array( "records" ) ) {
        std::cerr << "fold dump: fixture has no records array\n";
        return false;
    }
    for( JsonObject record : root.get_array( "records" ) ) {
        spawn_request request;
        request.id = itype_id( record.get_string( "id" ) );
        request.has_charges = record.get_bool( "has_charges", false );
        request.charges = record.get_int( "charges", 0 );
        request.save_json = record.get_string( "save_json", std::string() );
        requests.push_back( request );
    }
    return true;
}

auto load_packs() -> bool
{
    std::vector<mod_id> packs;
    packs.push_back( mod_management::get_default_core_content_pack() );
    const mod_id exotic( "exotic_ammo" );
    if( exotic.is_valid() ) {
        packs.push_back( exotic );
    }
    try {
        init::load_modfiles_for_dump( packs );
    } catch( const std::exception &err ) {
        std::cerr << "fold dump: error loading data: " << err.what() << '\n';
        return false;
    }
    return true;
}

auto dump_baseline( const std::vector<spawn_request> &requests ) -> bool
{
    JsonOut js( std::cout );
    js.start_object();
    js.member( "format", 1 );
    js.member( "kind", "baseline" );
    js.member( "records" );
    js.start_array();
    for( const spawn_request &request : requests ) {
        js.start_object();
        js.member( "id", request.id.str() );
        if( !request.id.is_valid() ) {
            js.member( "has_charges", request.has_charges );
            js.member( "charges", request.charges );
            js.member( "invalid", true );
            js.member( "props" );
            js.write_null();
            js.end_object();
            continue;
        }
        detached_ptr<item> spawned = spawn_with_charges( request.id, request );
        if( !spawned ) {
            js.member( "has_charges", request.has_charges );
            js.member( "charges", request.charges );
            js.member( "invalid", true );
            js.member( "props" );
            js.write_null();
            js.end_object();
            continue;
        }
        js.member( "has_charges", request.has_charges );
        js.member( "charges", request.charges );
        js.member( "props" );
        write_item_props( js, *spawned );
        js.member( "save_json", serialize_item( *spawned ) );
        js.end_object();
    }
    js.end_array();
    js.end_object();
    return true;
}

auto dump_fork( const std::vector<spawn_request> &requests ) -> bool
{
    JsonOut js( std::cout );
    js.start_object();
    js.member( "format", 1 );
    js.member( "kind", "fork" );
    js.member( "records" );
    js.start_array();
    for( const spawn_request &request : requests ) {
        const itype_id replacement = item_controller->migrate_id( request.id );
        js.start_object();
        js.member( "id", request.id.str() );
        if( !replacement.is_valid() ) {
            js.member( "has_charges", request.has_charges );
            js.member( "charges", request.charges );
            js.member( "invalid", true );
            js.member( "fresh" );
            js.write_null();
            js.member( "migrated" );
            js.write_null();
            js.end_object();
            continue;
        }
        js.member( "has_charges", request.has_charges );
        js.member( "charges", request.charges );
        js.member( "replacement", replacement.str() );

        // Fresh spawn of the replacement: what mapgen and item groups create today.
        detached_ptr<item> fresh = spawn_with_charges( replacement, request );
        if( fresh ) {
            item_controller->migrate_item( request.id, *fresh );
            js.member( "fresh" );
            write_item_props( js, *fresh );
        } else {
            js.member( "fresh" );
            js.write_null();
        }

        // Real save-load path: deserialize the mainline item and let the loader migrate it.
        if( !request.save_json.empty() ) {
            std::istringstream in( request.save_json );
            JsonIn jsin( in );
            detached_ptr<item> migrated = item::spawn( jsin );
            if( migrated ) {
                js.member( "migrated" );
                write_item_props( js, *migrated );
            } else {
                js.member( "migrated" );
                js.write_null();
            }
        } else {
            js.member( "migrated" );
            js.write_null();
        }
        js.end_object();
    }
    js.end_array();
    js.end_object();
    return true;
}

} // namespace

auto dump_folded_items( const std::vector<std::string> &opts ) -> bool
{
    if( opts.empty() ) {
        std::cerr << "fold dump: expected an input file\n";
        return false;
    }
    if( !load_packs() ) {
        return false;
    }
    bool fork_mode = false;
    {
        std::ifstream probe( opts[0] );
        if( !probe ) {
            std::cerr << "fold dump: cannot open " << opts[0] << '\n';
            return false;
        }
        JsonIn jsin( probe );
        fork_mode = !jsin.test_array();
    }
    std::vector<spawn_request> requests;
    bool ok = false;
    if( fork_mode ) {
        ok = read_fixture( opts[0], requests ) && dump_fork( requests );
    } else {
        ok = read_requests( opts[0], requests ) && dump_baseline( requests );
    }
    // The dump is complete; skip process teardown (Lua/dynamic-loader destruction crashes in
    // this headless mode) so a repeatable check gets a clean exit status.
    std::cout.flush();
    std::_Exit( ok ? 0 : 1 );
}
