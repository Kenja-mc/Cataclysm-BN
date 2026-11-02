import unittest

from agent_actions import actions_for, classify_screen, framed_title, menu_rows


MODERN_MENU = "\n".join([
    "│ a Background HUD row │",
    " " * 56 + "╭" + "─" * 27 + "╮",
    " " * 56 + "│ MAIN MENU                 │",
    " " * 56 + "├" + "─" * 27 + "┤",
    " " * 49 + "....0,,│ O Options                 │───────────╮",
    "map and HUD prose".ljust(56) + "│ ? Keybindings             │ z Outside HUD │",
    " " * 56 + "╰" + "─" * 27 + "╯",
    "│ b Message log row │ [Outside bracketed text]",
])


class MenuObserverTests(unittest.TestCase):
    def test_modern_menu_owns_its_rectangle_despite_background_glyphs(self):
        rows = menu_rows(MODERN_MENU)
        self.assertEqual([(row.hotkey, row.label) for row in rows], [("O", "Options")])
        self.assertEqual((rows[0].x, rows[0].y), (60, 4))
        self.assertEqual(menu_rows(MODERN_MENU, limit=1), rows)
        self.assertEqual(framed_title(MODERN_MENU), "MAIN MENU")
        self.assertEqual(classify_screen(MODERN_MENU), "ingame_menu")
        actions = {action.id: action for action in actions_for(
            MODERN_MENU, mode="curses", scheme="modern", mouse=True)}
        self.assertEqual(actions["press_O"].keys, ("O",))
        self.assertEqual(actions["click_O"].click, (60, 4))
        self.assertEqual(actions["click_O"].clicks, 2)
        self.assertNotIn("press_a", actions)
        self.assertNotIn("press_b", actions)
        self.assertNotIn("press_z", actions)
        for action in actions.values():
            self.assertNotIn("HUD", action.label)
            self.assertNotIn("Message log", action.label)
            self.assertNotIn("Outside bracketed", action.label)

    def test_modern_action_and_generic_uilist_headers_keep_menu_actions(self):
        for title, classification in (("Actions", "action_menu"), ("Choose action", "menu")):
            with self.subTest(title=title):
                screen = MODERN_MENU.replace("MAIN MENU                 ", title.ljust(26))
                self.assertEqual(framed_title(screen), title)
                self.assertEqual(classify_screen(screen), classification)
                actions = {action.id: action for action in actions_for(
                    screen, mode="curses", scheme="modern", mouse=True)}
                self.assertEqual(actions["press_O"].keys, ("O",))
                self.assertEqual(actions["click_O"].clicks, 2)

    def test_classic_inline_titles_bound_rows_and_keep_keyboard_actions(self):
        screen = "\n".join([
            "│ a Background HUD row │",
            "map0 ╭< MAIN MENU >───────╮",
            "map0 │ O Options          │ z Outside HUD │",
            "map0 ╰────────────────────╯",
            "│ b Message log row │",
        ])
        self.assertEqual(framed_title(screen), "MAIN MENU")
        self.assertEqual(classify_screen(screen), "ingame_menu")
        self.assertEqual([(row.hotkey, row.label) for row in menu_rows(screen)],
                         [("O", "Options")])
        actions = {action.id: action for action in actions_for(
            screen, mode="curses", scheme="classic", mouse=True)}
        self.assertEqual(actions["press_O"].keys, ("O",))
        self.assertNotIn("click_O", actions)

    def test_title_screen_brackets_read_the_real_colored_shortcut(self):
        screen = "Cataclysm: Bright Nights\n[New Game] [MOTD]"
        colored = "Cataclysm: Bright Nights\n[\x1b[32mN\x1b[37mew Game] [MOTD]"
        self.assertEqual(classify_screen(screen), "main_menu")
        rows = menu_rows(screen, colored=colored)
        self.assertEqual([(row.hotkey, row.label) for row in rows], [("N", "New Game")])
        actions = {action.id: action for action in actions_for(
            screen, mode="curses", colored=colored, mouse=True)}
        self.assertEqual(actions["press_N"].keys, ("N",))
        self.assertNotIn("click_N", actions)


if __name__ == "__main__":
    unittest.main()
