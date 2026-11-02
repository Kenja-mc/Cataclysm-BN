#pragma once

#include <string>
#include <vector>

class avatar;

namespace test_state
{

struct row {
    std::string text;
    std::string hotkey;
    bool enabled = true;
};

void set_path( const std::string &path );
auto enabled() -> bool;
void on_turn( const avatar &you );
void refresh_overlays( const avatar &you );
void input_wait( bool waiting );
void ui_show( const std::string &id, const std::string &title,
              const std::vector<row> &rows, int selected );
void ui_close( const std::string &id );

}
