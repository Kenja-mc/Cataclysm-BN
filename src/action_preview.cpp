#include "action_preview.h" // IWYU pragma: associated

#include "bodypart.h"
#include "character.h"
#include "character_encumbrance.h"
#include "color.h"
#include "item.h"
#include "output.h"
#include "ranged.h"
#include "string_formatter.h"
#include "string_utils.h"
#include "translations.h"
#include "units.h"

#include <algorithm>
#include <ranges>
#include <string>
#include <vector>

static const skill_id skill_swimming( "swimming" );

auto encumb_color( int level ) -> nc_color
{
    if( level < 0 ) {
        return c_green;
    }
    if( level < 10 ) {
        return c_light_gray;
    }
    if( level < 40 ) {
        return c_yellow;
    }
    if( level < 70 ) {
        return c_light_red;
    }
    return c_red;
}

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
                change.sharing.push_back( worn_item->tname() );
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
                                         encumb_color( change.after ) ) );
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
