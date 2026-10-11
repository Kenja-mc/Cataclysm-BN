#include "item_thumbnail.h"

#include <optional>
#include <unordered_map>
#include <utility>

#include "bodypart.h"
#include "damage.h"
#include "flag.h"
#include "item.h"
#include "itype.h"
#include "options.h"
#include "skill.h"
#include "string_id.h"

namespace
{

auto thumb( const char *id ) -> ascii_art_id
{
    return ascii_art_id( id );
}

auto gun_thumbnail( const item &it ) -> std::optional<ascii_art_id>
{
    if( it.type->gun == nullptr ) {
        return std::nullopt;
    }
    static const std::unordered_map<skill_id, ascii_art_id> by_skill {
        { skill_id( "pistol" ), thumb( "thumb_gun_pistol" ) },
        { skill_id( "rifle" ), thumb( "thumb_gun_rifle" ) },
        { skill_id( "shotgun" ), thumb( "thumb_gun_shotgun" ) },
        { skill_id( "smg" ), thumb( "thumb_gun_smg" ) },
        { skill_id( "launcher" ), thumb( "thumb_gun_launcher" ) },
        { skill_id( "archery" ), thumb( "thumb_gun_bow" ) },
    };
    const auto found = by_skill.find( it.type->gun->skill_used );
    return found != by_skill.end() ? std::optional( found->second ) : std::nullopt;
}

auto melee_thumbnail( const item &it ) -> std::optional<ascii_art_id>
{
    if( !it.is_melee() ) {
        return std::nullopt;
    }
    if( it.has_flag( flag_SPEAR ) ) {
        return thumb( "thumb_melee_spear" );
    }
    return it.damage_melee( DT_CUT ) > it.damage_melee( DT_BASH )
           ? thumb( "thumb_melee_blade" )
           : thumb( "thumb_melee_blunt" );
}

auto armor_thumbnail( const item &it ) -> std::optional<ascii_art_id>
{
    if( it.find_armor_data() == nullptr ) {
        return std::nullopt;
    }
    const body_part_set covered = it.get_covered_body_parts();
    const auto is_covered = [&covered]( const bodypart_str_id & bp ) {
        return covered.test( bp );
    };
    const bool head = is_covered( body_part_head );
    const bool torso = is_covered( body_part_torso );
    const bool legs = is_covered( body_part_leg_l ) || is_covered( body_part_leg_r );
    const bool feet = is_covered( body_part_foot_l ) || is_covered( body_part_foot_r );
    const bool hands = is_covered( body_part_hand_l ) || is_covered( body_part_hand_r );

    if( head && !torso && !legs ) {
        return thumb( "thumb_armor_head" );
    }
    if( torso && legs ) {
        return thumb( "thumb_armor_full" );
    }
    if( legs && !torso ) {
        return thumb( "thumb_armor_legs" );
    }
    if( feet && !torso && !legs ) {
        return thumb( "thumb_armor_feet" );
    }
    if( hands && !torso && !legs && !feet ) {
        return thumb( "thumb_armor_hands" );
    }
    return thumb( "thumb_armor_torso" );
}

auto kind_thumbnail( const item &it ) -> std::optional<ascii_art_id>
{
    if( it.is_ammo() ) {
        return thumb( "thumb_ammo" );
    }
    if( it.is_magazine() ) {
        return thumb( "thumb_magazine" );
    }
    if( it.is_battery() ) {
        return thumb( "thumb_battery" );
    }
    if( it.is_medication() ) {
        return thumb( "thumb_med" );
    }
    if( it.is_book() ) {
        return thumb( "thumb_book" );
    }
    if( it.is_container() ) {
        return thumb( "thumb_container" );
    }
    if( it.is_food() ) {
        return it.get_comestible()->comesttype == "DRINK"
               ? thumb( "thumb_drink" )
               : thumb( "thumb_food" );
    }
    if( it.is_tool() ) {
        return thumb( "thumb_tool" );
    }
    return thumb( "thumb_generic" );
}

} // namespace

auto thumbnail_for( const item &it ) -> std::optional<ascii_art_id>
{
    if( it.is_null() || it.type->picture_id.is_valid() ||
        !get_option<bool>( "ENABLE_ASCII_ART_ITEM" ) ) {
        return std::nullopt;
    }
    for( const auto &pick : { &gun_thumbnail, &melee_thumbnail, &armor_thumbnail, &kind_thumbnail } ) {
        if( const std::optional<ascii_art_id> art = pick( it ) ) {
            return art;
        }
    }
    return std::nullopt;
}
