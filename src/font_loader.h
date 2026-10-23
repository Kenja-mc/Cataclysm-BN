#pragma once

#include <algorithm>
#include <stdexcept>
#include <string>
#include <vector>

#include "debug.h"
#include "filesystem.h"
#include "fstream_utils.h"
#include "json.h"
#include "path_info.h"
#include "cata_utility.h"

// Ensure that unifont is always loaded as a fallback font to prevent users from shooting themselves in the foot
void ensure_unifont_loaded( std::vector<std::string> &font_list );

// Ensure the bundled icon font (before unifont) and unifont end every typeface fallback list,
// including user fonts.json files written before the icon font existed.
void ensure_fallback_fonts_loaded( std::vector<std::string> &font_list );

class font_loader
{
    public:
        bool fontblending = true;
        std::vector<std::string> typeface;
        std::vector<std::string> map_typeface;
        std::vector<std::string> overmap_typeface;
        int fontwidth = 11;
        int fontheight = 24;
        int fontsize = 18;
        int map_fontwidth = 24;
        int map_fontheight = 24;
        int map_fontsize = 18;
        int overmap_fontwidth = 24;
        int overmap_fontheight = 24;
        int overmap_fontsize = 18;

    private:
        void load_throws( const std::string &path );

    public:
        void load();
};


