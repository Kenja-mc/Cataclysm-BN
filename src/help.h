#pragma once

#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "cursesdef.h"
#include "input.h"
#include "point.h"

class JsonIn;

class help
{
    public:
        void load();
        void display_help();

    private:
        void deserialize( JsonIn &jsin );
        void draw_menu( const catacurses::window &win, const std::optional<size_t> &selected );
        std::string get_note_colors();
        std::string get_dir_grid();

        std::map<int, std::pair<std::string, std::vector<std::string> > > help_texts;
        std::vector< std::vector<std::string> > hotkeys;
        /// Window-relative start and printed width of each rendered topic row, in the same
        /// order as the hotkeys vector. Filled by draw_menu, read by the click handler.
        std::vector<std::pair<point, int>> menu_rows;

        input_context ctxt;
};

help &get_help();

std::string get_hint();

/// Replaces `<press_action>` tags with the first key bound to that action, e.g. "w".
/// `<press_action:CONTEXT>` uses that input context's binding, e.g. `<press_QUIT:TARGET>`.
std::string expand_key_tags( const std::string &text );


