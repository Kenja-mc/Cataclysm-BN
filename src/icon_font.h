#pragma once
/// Glyphs in the bundled icon font (data/font/bno-icons.ttf), which the tiles build always loads.
namespace icon_font
{
/// Pinhead stance figures; two cells wide.
inline constexpr auto walk = "\U0010F000";
inline constexpr auto run = "\U0010F001";
inline constexpr auto crouch = "\U0010F002";
inline constexpr auto prone = "\U0010F003";
/// Two-cell copies of the Material Design Icons the HUD uses.
inline constexpr auto weather_sunny = "\U0010F010";
inline constexpr auto weather_night = "\U0010F011";
inline constexpr auto weather_cloudy = "\U0010F012";
inline constexpr auto weather_rainy = "\U0010F013";
inline constexpr auto weather_lightning = "\U0010F014";
inline constexpr auto weather_snowy = "\U0010F015";
inline constexpr auto weather_fog = "\U0010F016";
inline constexpr auto stairs_down = "\U0010F017";
inline constexpr auto boxing_glove = "\U0010F018";
inline constexpr auto sword = "\U0010F019";
inline constexpr auto pistol = "\U0010F01A";
inline constexpr auto bow_arrow = "\U0010F01B";
inline constexpr auto karate = "\U0010F01C";
inline constexpr auto mdi_walk = "\U0010F01D";
inline constexpr auto mdi_run = "\U0010F01E";
inline constexpr auto star_four_points = "\U0010F01F";
inline constexpr auto compass = "\U0010F020";
inline constexpr auto gas_station = "\U0010F021";
inline constexpr auto battery = "\U0010F022";
inline constexpr auto bandage = "\U0010F023";
inline constexpr auto cup_water = "\U0010F024";
inline constexpr auto food_drumstick = "\U0010F025";
inline constexpr auto power_sleep = "\U0010F026";
inline constexpr auto thermometer = "\U0010F027";
inline constexpr auto clock_outline = "\U0010F028";
inline constexpr auto lightbulb_on = "\U0010F029";
inline constexpr auto weather_windy = "\U0010F02A";
inline constexpr auto check = "\U0010F02B";
inline constexpr auto moon_new = "\U0010F02C";
inline constexpr auto moon_waxing_crescent = "\U0010F02D";
inline constexpr auto moon_first_quarter = "\U0010F02E";
inline constexpr auto moon_waxing_gibbous = "\U0010F02F";
inline constexpr auto moon_full = "\U0010F030";
inline constexpr auto moon_waning_gibbous = "\U0010F031";
inline constexpr auto moon_last_quarter = "\U0010F032";
inline constexpr auto moon_waning_crescent = "\U0010F033";
/// Whether this build draws text with SDL fonts and so has the bundled icon font.
#if defined(TILES)
inline constexpr auto bundled = true;
#else
inline constexpr auto bundled = false;
#endif
} // namespace icon_font
