#pragma once

class avatar;

/// One-line tips the first time a character meets a situation (hunger, night, a hostile...),
/// in the spirit of Caves of Qud's tutorial hints. Each shows once per character.
namespace first_tips
{

auto check( avatar &you ) -> void;

} // namespace first_tips
