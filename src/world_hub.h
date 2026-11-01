#pragma once

#include <memory>
#include <string>
#include <vector>

#include "cursesdef.h"
#include "input.h"

class achievements_tracker;
class kill_tracker;
class stats_tracker;

/// The World page: missions, factions, zones and scores as numbered tabs on one page.
namespace world_hub
{

/// The page that owns a panel, so a panel can step out of the way for a full-screen modal such
/// as zone point selection, where the map must be visible instead of the page.
class host
{
    public:
        virtual ~host() = default;
        /// Hide the page windows and stop drawing until restore().
        virtual void hide() = 0;
        /// Bring the page back after hide().
        virtual void restore() = 0;
};

/// One tab's screen. It draws into the page's body and handles its own actions, so its state
/// survives while another tab is shown.
class panel
{
    public:
        virtual ~panel() = default;
        /// The name shown on the numbered tab strip.
        virtual auto name() const -> std::string = 0;
        /// Re-read the data this tab shows; called before the page draws it.
        virtual void refresh() {}
        /// Draw the tab's content into the page body and flush the window.
        virtual void draw( const catacurses::window &body, input_context &ctxt ) = 0;
        /// Handle one action. The page keeps Esc and Left/Right (leaving and switching tabs);
        /// a panel receives NEXT_TAB and PREV_TAB for its own inner pages instead.
        virtual void handle( const std::string &action, input_context &ctxt,
                             const catacurses::window &body, host &page ) = 0;
        /// Called once when the page closes, before it returns to play.
        virtual void close() {}
};

using panel_ptr = std::unique_ptr<panel>;

auto missions_screen() -> panel_ptr;
auto factions_screen() -> panel_ptr;
auto zones_screen() -> panel_ptr;
auto scores_screen( const achievements_tracker &achievements, stats_tracker &stats,
                    const kill_tracker &kills ) -> panel_ptr;

/// Draws the World page with its numbered tabs and loops until the player presses Esc.
auto show( std::vector<panel_ptr> screens ) -> void;

} // namespace world_hub
