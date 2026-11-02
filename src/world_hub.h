#pragma once

#include <memory>
#include <string>
#include <vector>

#include "cursesdef.h"
#include "input.h"

class achievements_tracker;
class kill_tracker;
class stats_tracker;

namespace world_hub
{

class host
{
    public:
        virtual ~host() = default;
        virtual auto hide() -> void = 0;
        virtual auto restore() -> void = 0;
};

class panel
{
    public:
        virtual ~panel() = default;
        virtual auto name() const -> std::string = 0;
        virtual auto refresh() -> void {}
        virtual auto draw( const catacurses::window &body, input_context &ctxt ) -> void = 0;
        virtual auto handle( const std::string &action, input_context &ctxt,
                             const catacurses::window &body, host &page ) -> void = 0;
        virtual auto close() -> void {}
};

using panel_ptr = std::unique_ptr<panel>;

auto missions_screen() -> panel_ptr;
auto factions_screen() -> panel_ptr;
auto zones_screen() -> panel_ptr;
auto scores_screen( const achievements_tracker &achievements, stats_tracker &stats,
                    const kill_tracker &kills ) -> panel_ptr;

auto show( std::vector<panel_ptr> screens, size_t start_tab = 0 ) -> void;

auto show_in_sidebar( std::vector<panel_ptr> screens ) -> void;

}
