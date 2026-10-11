#pragma once

#include <optional>

#include "ascii_art.h"

class item;

/**
 * Generic art drawn as a thumbnail for items that have no picture of their own.
 * Returns the art to show, or nothing when the item kind has no thumbnail.
 */
auto thumbnail_for( const item &it ) -> std::optional<ascii_art_id>;
