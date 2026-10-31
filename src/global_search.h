#pragma once

#include <string>
#include <vector>

#include "coordinates.h"

class avatar;
class input_context;
class map;
struct input_event;

/**
 * One key that searches everything the screen can do and everything the player knows.
 *
 * On the map it finds the controls of the map screen, the creatures the player has detected,
 * and the terrain, furniture, traps and items the player can see now or has seen before.  In a
 * menu it finds that menu's own controls.  Picking a control runs it.  Picking a map object only
 * moves the existing cursor onto it (the reticle for seen ground, the view for memory), so a
 * search never acts on the world or spends time; canceling puts the cursor back.
 */
namespace global_search
{

/// A search result.
struct target {
    enum class kind {
        control,    ///< an action the current screen handles
        creature,   ///< a creature the player has detected
        sighted,    ///< terrain, furniture, trap or items the player can see right now
        remembered  ///< terrain, furniture or a trap map memory holds
    };

    kind type = kind::control;
    /// Action ident for controls; empty for map objects.
    std::string ident;
    /// Player-visible name.
    std::string label;
    /// How to reach a control, or where a map object is.
    std::string detail;
    /// Map object position, in bubble coordinates; unused for controls.
    tripoint_bub_ms pos;
    /// Distance from the player in tiles; unused for controls.
    int distance = 0;
    /// Whether this entry has a cursor to move to.  Seen things use the targeting reticle; a
    /// remembered tile pans the view onto what map memory draws.
    bool selectable = false;
    /// The text queries are matched against (name plus aliases).
    std::string match_text;
};

/**
 * Whether this key press opens the palette on the given screen.
 *
 * False in screens that take free text, where the key belongs to the text field, and when the
 * player has not bound the search action.
 */
auto opens_here( const input_event &evt, const input_context &origin ) -> bool;

/**
 * Show the palette over the current screen.
 *
 * @return The action ident to run, or an empty string when the player canceled or picked a map
 * object.  A picked map object leaves the cursor on it; canceling, or picking a control instead,
 * restores the cursor the screen had before.  Never returns the search action itself.
 */
auto run( const input_context &origin ) -> std::string;

/**
 * Put the existing cursor on a target without running anything.
 *
 * Anything the player can see gets the targeting reticle and the tile inspector.  A remembered
 * tile instead pans the view onto what map memory draws: the reticle is never placed on unseen
 * ground, and the tile inspector stays closed, because it would read the live map rather than the
 * memory the player is being shown.
 *
 * @return Whether a cursor moved.
 */
auto focus( const target &what ) -> bool;

/**
 * The map objects the palette may offer: everything the player can see on their own floor, every
 * creature they have detected, and what map memory remembers nearby.  Anything hidden by walls,
 * darkness or a sealed container is absent, and remembered rows name only what memory holds, never
 * what stands there now.  Controls are not included.
 */
auto map_targets( const avatar &you, map &here ) -> std::vector<target>;

} // namespace global_search
