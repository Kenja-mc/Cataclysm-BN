#pragma once

#include <string>

#include "action.h"

auto action_route( action_id act ) -> std::string;

auto action_route( const std::string &id ) -> std::string;

auto action_route( const std::string &id, const std::string &context ) -> std::string;
