#pragma once

#include <chrono>
#include <functional>
#include <string>

namespace music
{

enum class context {
    title,
    explore,
    danger,
    night,
    underground,
    vehicle,
    shelter,
};

auto context_id( context ctx ) -> const char *;

struct signals {
    bool danger = false;
    bool vehicle = false;
    bool underground = false;
    bool night = false;
    bool shelter = false;
    bool sleeping = false;
};

struct timing {
    std::chrono::seconds minimum_play{ 20 };
    std::chrono::seconds danger_release{ 5 };
    std::chrono::seconds candidate_hold{ 4 };
};

class scheduler
{
    public:
        explicit scheduler( timing t = {} );

        auto update( const signals &state, std::chrono::steady_clock::time_point now ) -> context;
        auto current() const -> context {
            return current_;
        }
        auto changed() const -> bool {
            return changed_;
        }
        auto reset() -> void;

    private:
        auto priority_context( const signals &state ) const -> context;
        auto switch_to( context next, std::chrono::steady_clock::time_point now ) -> void;

        timing timing_;
        context current_ = context::title;
        context candidate_ = context::title;
        std::chrono::steady_clock::time_point changed_at_{};
        std::chrono::steady_clock::time_point candidate_since_{};
        std::chrono::steady_clock::time_point danger_clear_since_{};
        bool danger_clearing_ = false;
        bool started_ = false;
        bool changed_ = false;
};

auto resolve_playlist( context ctx,
                       const std::function<bool( const std::string & )> &has_playlist ) -> std::string;

auto update( bool force = false ) -> void;
auto pump() -> void;
auto danger_music_active() -> bool;
auto resume() -> void;
auto reset() -> void;
auto current_context() -> context;
auto current_playlist() -> std::string;

}
