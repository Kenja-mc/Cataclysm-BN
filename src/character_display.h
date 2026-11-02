#pragma once

#include "character_stat.h"
#include "color.h"

class Character;
class item;
class avatar;
class ui_adaptor;

namespace catacurses
{
class window;
} // namespace catacurses

namespace character_display
{

/// The encumbrance from which the character sheet stops showing the normal encumbrance colour.
inline constexpr int encumb_notice = 10;

/// The colour the character sheet gives a body part's encumbrance.
auto encumb_color( int level ) -> nc_color;

/**
 * Formats and prints encumbrance info to specified window
 */
void print_encumbrance( ui_adaptor &ui, const catacurses::window &win, const Character &ch,
                        int line = -1,
                        const item *selected_clothing = nullptr );

/**
 * @brief Handles and displays detailed character info for the '@' screen.
 *
 * @param ch Character to display info for. Has to be non-const reference
 * to allow toggling skills and upgrading stats for stats-through-x mods.
 */
void disp_info( Character &ch );

/**
 * Handles upgrade of avatar stats.
 */
void upgrade_stat_prompt( avatar &you, const character_stat &stat );

/** Gets the minimum combined bare-handed damage from skill, bionics, and mutations for display functions */
int display_empty_handed_base_damage( const Character &you );

} // namespace character_display



