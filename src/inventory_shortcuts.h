#pragma once
#ifndef CATA_SRC_INVENTORY_SHORTCUTS_H
#define CATA_SRC_INVENTORY_SHORTCUTS_H

#include "inventory.h"

inline auto invlet_is_manual_digit( int invlet ) -> bool { return invlet >= '0' && invlet <= '9'; }

/// Keep saved numeric shortcuts without adding them to automatic assignment.
inline auto invlet_is_kept( int invlet ) -> bool
{
    return inv_chars.valid( invlet ) || invlet_is_manual_digit( invlet );
}

#endif // CATA_SRC_INVENTORY_SHORTCUTS_H
