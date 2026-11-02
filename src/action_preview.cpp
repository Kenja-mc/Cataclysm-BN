#include "action_preview.h" // IWYU pragma: associated

#include "character_display.h"
#include "avatar.h"
#include "avatar_functions.h"
#include "bodypart.h"
#include "calendar.h"
#include "character.h"
#include "character_encumbrance.h"
#include "color.h"
#include "game_constants.h"
#include "item.h"
#include "itype.h"
#include "output.h"
#include "ranged.h"
#include "recipe.h"
#include "recipe_dictionary.h"
#include "string_formatter.h"
#include "string_utils.h"
#include "translations.h"
#include "units.h"

#include <algorithm>
#include <ranges>
#include <string>
#include <string_view>
#include <vector>

static const skill_id skill_swimming( "swimming" );

auto encumbrance_numbers( const Character &who, const bodypart_str_id &bp, int value )
-> encumbrance_effect_numbers
{
    auto numbers = encumbrance_effect_numbers{};
    const auto swim_skill = who.get_skill_level( skill_swimming );

    if( bp == body_part_torso ) {
        numbers.melee_hit = std::max( -value, -80 );
        numbers.dodge = -( value / 10.0 );
        numbers.swim_cost = ( value / 10.0 ) * ( 80 - swim_skill * 3 );
        numbers.melee_cost = value;
    } else if( bp == body_part_eyes ) {
        numbers.perception = -( value / 10 );
        numbers.dispersion = value * 10;
        numbers.night_vision = vision::nv_range_from_eye_encumbrance( value );
    } else if( bp == body_part_mouth ) {
        numbers.mouth_stamina = -( value / 5 );
    } else if( bp == body_part_arm_l || bp == body_part_arm_r ) {
        numbers.melee_stamina = value * 2;
        numbers.ranged_dispersion = value / 5.0;
    } else if( bp == body_part_hand_l || bp == body_part_hand_r ) {
        numbers.reload_cost = ( value / 10 ) * 15;
        numbers.throw_dex = -( value / 10.0f );
        numbers.hand_melee_cost = value / 2;
        numbers.aim_speed = ranged::aim_speed_encumbrance_modifier( who );
    } else if( bp == body_part_leg_l || bp == body_part_leg_r ) {
        numbers.run_cost = static_cast<int>( value * 0.15 );
        numbers.swim_cost = ( value / 10 ) * ( 50 - swim_skill * 2 ) / 2;
        numbers.dodge = -value / 10.0 / 4.0;
    } else if( bp == body_part_foot_l || bp == body_part_foot_r ) {
        numbers.run_cost = static_cast<int>( value * 0.25 );
    }

    return numbers;
}

auto encumbrance_effects( const Character &who, const bodypart_str_id &bp, int value )
-> std::string
{
    const auto numbers = encumbrance_numbers( who, bp, value );

    if( bp == body_part_torso ) {
        return string_format( _( "melee hit %+d%%, dodge %+d" ),
                              numbers.melee_hit, static_cast<int>( numbers.dodge ) );
    }
    if( bp == body_part_head ) {
        return _( "limits what you can wear" );
    }
    if( bp == body_part_eyes ) {
        return string_format( _( "perception %+d, dispersion %+d, night vision %+.1f" ),
                              numbers.perception, numbers.dispersion, numbers.night_vision );
    }
    if( bp == body_part_mouth ) {
        return string_format( _( "breath stamina %+d" ), numbers.mouth_stamina );
    }
    if( bp == body_part_arm_l || bp == body_part_arm_r ) {
        return string_format( _( "melee stamina %+d, ranged dispersion %+.1f" ),
                              numbers.melee_stamina, numbers.ranged_dispersion );
    }
    if( bp == body_part_hand_l || bp == body_part_hand_r ) {
        return string_format( _( "reload %+d, throwing %+.1f, melee cost %+d, aim speed %+.1f" ),
                              numbers.reload_cost, numbers.throw_dex, numbers.hand_melee_cost,
                              numbers.aim_speed );
    }
    if( bp == body_part_leg_l || bp == body_part_leg_r ) {
        return string_format( _( "run cost %+d, dodge %+.1f" ), numbers.run_cost, numbers.dodge );
    }
    if( bp == body_part_foot_l || bp == body_part_foot_r ) {
        return string_format( _( "run cost %+d" ), numbers.run_cost );
    }

    return std::string();
}

auto preview_wear( const Character &who, const item &it ) -> wear_preview
{
    auto preview = wear_preview{};
    const auto current = who.get_encumbrance();
    const auto layered = who.get_encumbrance( it );
    const auto covered = it.get_covered_body_parts();

    for( const bodypart_id &bp : who.get_all_body_parts() ) {
        if( !covered.test( bp.id() ) ) {
            continue;
        }
        const auto current_it = current.elems.find( bp.id() );
        const auto layered_it = layered.elems.find( bp.id() );
        if( current_it == current.elems.end() || layered_it == layered.elems.end() ) {
            continue;
        }

        auto change = body_change{ .part = bp,
                                   .before = current_it->second.encumbrance,
                                   .after = layered_it->second.encumbrance,
                                   .layering_after = layered_it->second.layer_penalty };
        for( const item * const &worn_item : who.worn ) {
            if( worn_item->get_layer() == it.get_layer() && worn_item->covers( bp ) ) {
                change.sharing.push_back( worn_item->tname( 1, false ) );
            }
        }
        preview.parts.push_back( std::move( change ) );
    }

    preview.warmth_delta = it.get_warmth();
    preview.storage_delta = it.get_storage();
    preview.moves = who.item_wear_cost( it );
    return preview;
}

namespace
{

auto wear_time_text( int moves ) -> std::string
{
    return string_format( _( "%d s" ), std::max( 1, moves / 100 ) );
}

auto part_line( const Character &who, const body_change &change ) -> std::string
{
    auto line = string_format( "%s %d → %s", body_part_name_as_heading( change.part, 1 ),
                               change.before,
                               colorize( std::to_string( change.after ),
                                         character_display::encumb_color( change.after ) ) );
    if( !change.sharing.empty() ) {
        line += string_format( " (%s)", string_format( _( "layering +%d with %s" ),
                               change.layering_after,
                               enumerate_as_string( change.sharing ) ) );
    }
    const auto effects = encumbrance_effects( who, change.part.id(), change.after );
    if( !effects.empty() ) {
        line += " · " + effects;
    }
    return line;
}

} // namespace

auto describe( const Character &who, const wear_preview &preview ) -> std::vector<std::string>
{
    auto lines = std::vector<std::string>();
    auto changed = std::vector<const body_change *>();
    for( const body_change &part : preview.parts ) {
        if( part.after != part.before ) {
            changed.push_back( &part );
        }
    }

    if( changed.empty() ) {
        lines.push_back( _( "No encumbrance change" ) );
    } else {
        lines.push_back( part_line( who, *changed.front() ) );
        if( changed.size() > 1 ) {
            auto rest = std::vector<std::string>();
            for( const body_change *part : changed | std::views::drop( 1 ) ) {
                rest.push_back( part_line( who, *part ) );
            }
            lines.push_back( join( rest, " · " ) );
        }
    }

    auto summary = std::vector<std::string>();
    if( preview.warmth_delta != 0 ) {
        summary.push_back( string_format( _( "Warmth %+d" ), preview.warmth_delta ) );
    }
    if( preview.storage_delta > 0_ml ) {
        summary.push_back( string_format( _( "Storage +%s" ),
                                          format_volume( preview.storage_delta ) ) );
    }
    if( preview.moves > 0 ) {
        summary.push_back( wear_time_text( preview.moves ) );
    }
    if( !summary.empty() ) {
        lines.push_back( join( summary, " · " ) );
    }

    return lines;
}

namespace
{

auto action_time_text( int moves ) -> std::string
{
    if( moves >= to_moves<int>( 1_minutes ) ) {
        return to_string_approx( time_duration::from_turns( moves / to_moves<int>( 1_turns ) ), false );
    }
    return string_format( _( "%d s" ), std::max( 1, moves / to_moves<int>( 1_turns ) ) );
}

auto wear_cost( const Character &who, const item &it ) -> std::string
{
    const auto preview = preview_wear( who, it );
    auto parts = std::vector<std::string>();
    if( preview.moves > 0 ) {
        parts.push_back( action_time_text( preview.moves ) );
    }
    const auto worst = std::ranges::max_element( preview.parts, {},
    []( const body_change &part ) {
        return part.after - part.before;
    } );
    if( worst != preview.parts.end() && worst->after > worst->before ) {
        parts.push_back( string_format( _( "%s %+d" ),
                                        to_lower_case( body_part_name_as_heading( worst->part, 1 ) ),
                                        worst->after - worst->before ) );
    }
    return join( parts, " · " );
}

auto put_away_text( const avatar &who, const item &weapon ) -> std::string
{
    if( !who.can_unwield( weapon ).success() ) {
        return std::string();
    }
    for( const item * const &worn : who.worn ) {
        if( worn->can_holster( weapon ) ) {
            return string_format( _( "%1$s → %2$s" ), weapon.tname( 1, false ), worn->tname( 1, false ) );
        }
    }
    if( who.volume_carried() + weapon.volume() <= who.volume_capacity() ) {
        return string_format( _( "%1$s → %2$s" ), weapon.tname( 1, false ), _( "inventory" ) );
    }
    return colorize( string_format( _( "%s drops" ), weapon.tname( 1, false ) ), c_light_red );
}

auto wield_cost( const avatar &who, const item &it ) -> std::string
{
    if( who.is_wielding( it ) ) {
        return std::string();
    }
    const int base = who.is_worn( it ) ? INVENTORY_HANDLING_PENALTY / 2 : INVENTORY_HANDLING_PENALTY;
    auto text = action_time_text( who.item_handling_cost( it, true, base ) );
    if( who.is_armed() ) {
        const auto destination = put_away_text( who, who.primary_weapon() );
        if( !destination.empty() ) {
            text += " · " + destination;
        }
    }
    return text;
}

auto eat_cost( const avatar &who, const item &it ) -> std::string
{
    item &food = who.get_consumable_from( const_cast<item &>( it ) );
    if( food.is_null() || !food.is_comestible() ) {
        return std::string();
    }
    auto readings = std::vector<std::string>();
    readings.push_back( action_time_text( who.consume_moves( food ) ) );
    const int kcal = who.compute_effective_nutrients( food ).kcal;
    if( kcal != 0 ) {
        readings.push_back( string_format( _( "%d kcal" ), kcal ) );
    }
    const int quench = who.can_eat( food ).success() ? food.get_comestible()->quench : 0;
    if( quench != 0 ) {
        readings.push_back( string_format( _( "quench %+d" ), quench ) );
    }
    const int joy = who.fun_for( food ).first;
    if( joy != 0 ) {
        readings.push_back( string_format( _( "joy %+d" ), joy ) );
    }
    return join( readings, " · " );
}

auto read_cost( const avatar &who, const item &it ) -> std::string
{
    if( !it.is_book() ) {
        return std::string();
    }
    const int moves = who.time_to_read( it, who );
    return moves > 0 ? action_time_text( moves ) : std::string();
}

auto disassemble_cost( const item &it ) -> std::string
{
    const recipe &r = recipe_dictionary::get_uncraft( it.typeId() );
    if( !r ) {
        return std::string();
    }
    auto parts = std::vector<std::string>();
    if( r.time > 0 ) {
        parts.push_back( action_time_text( r.time ) );
    }
    parts.push_back( _( "can't undo" ) );
    return join( parts, " · " );
}

} // namespace

auto action_cost( const avatar &who, const item &it, std::string_view action ) -> std::string
{
    if( action == "WEAR" ) {
        return wear_cost( who, it );
    }
    if( action == "WIELD" ) {
        return wield_cost( who, it );
    }
    if( action == "EAT" ) {
        return eat_cost( who, it );
    }
    if( action == "READ" ) {
        return read_cost( who, it );
    }
    if( action == "UNLOAD" ) {
        const int moves = avatar_funcs::unload_moves( who, it );
        return moves > 0 ? action_time_text( moves ) : std::string();
    }
    if( action == "DISASSEMBLE" ) {
        return disassemble_cost( it );
    }
    return std::string();
}
