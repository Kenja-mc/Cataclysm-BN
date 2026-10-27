#pragma once

#include <chrono>
#include <functional>
#include <string>

/**
 * Dynamic background music.
 *
 * The scheduler turns a snapshot of the game state into one context per turn.
 * Playlists live in the soundpack's musicset.json and are named after their
 * context; a context the soundpack does not provide falls back to "title".
 */
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

/// Timings that keep a passing threat from flipping the track back and forth.
struct timing {
    /// A non-danger context must play this long before another one replaces it.
    std::chrono::seconds minimum_play{ 20 };
    /// Danger leaves instantly but clears only after this long without a threat.
    std::chrono::seconds danger_release{ 5 };
    /// Any other context must stay the best choice for this long.
    std::chrono::seconds candidate_hold{ 4 };
};

class scheduler
{
    public:
        explicit scheduler( timing t = {} );

        /// Feed one state snapshot; returns the context that should be playing now.
        auto update( const signals &state, std::chrono::steady_clock::time_point now ) -> context;
        auto current() const -> context {
            return current_;
        }
        /// Whether the last update() changed the selected context.
        auto changed() const -> bool {
            return changed_;
        }
        void reset();

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

/**
 * Pick the playlist for a context. A context without a non-empty playlist in
 * the soundpack uses "title", which is today's single endless playlist.
 */
auto resolve_playlist( context ctx,
                       const std::function<bool( const std::string & )> &has_playlist ) -> std::string;

/// Read the game state, advance the scheduler and switch playlists when needed.
void update( bool force = false );
/// Service a track that ended, from the main thread (turn or frame pump).
void pump();
/// True when the danger context playlist is the track actually playing, so the
/// older danger ambience themes must stay quiet.
auto danger_music_active() -> bool;
/// Restart music after it was turned off, or start the title track outside a game.
void resume();
/// Forget the in-game context when returning to the title screen.
void reset();
/// The context selected by the last update, for Lua and diagnostics. Menu and
/// single-playlist mode report "title".
auto current_context() -> context;

} // namespace music
