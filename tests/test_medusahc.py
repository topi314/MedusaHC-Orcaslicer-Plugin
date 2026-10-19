import unittest

from medusahc import process


def _run(text, **flags):
    lines = text.splitlines(keepends=True)
    changed = process(lines, **flags)
    return changed, "".join(lines)


class ProcessTests(unittest.TestCase):
    def test_swaps_z_hop_and_xy_travel_and_moves_feedrate(self):
        changed, result = _run(
            "T0\n"
            "G1 E1.5\n"
            "G0 Z0.4 F9000\n"
            "G0 X10 Y20\n"
        )
        self.assertTrue(changed)
        self.assertEqual(
            result,
            "T0\n"
            "G1 E1.5\n"
            "G0 X10 Y20 F9000\n"
            "G0 Z0.4\n",
        )

    def test_leaves_feedrate_on_xy_travel_that_already_has_one(self):
        changed, result = _run("T1\nG1 Z1 F1000\nG1 X5 F3000\n")
        self.assertTrue(changed)
        self.assertEqual(result, "T1\nG1 X5 F3000\nG1 Z1 F1000\n")

    def test_skips_block_when_first_move_is_xy(self):
        source = "T0\nG1 E2\nG0 X1 Y2 F5000\nG0 Z0.4\n"
        changed, result = _run(source)
        self.assertFalse(changed)
        self.assertEqual(result, source)

    def test_converts_m109_only_after_first_layer_change(self):
        changed, result = _run(
            "M109 S200 ; heat\n"
            ";LAYER_CHANGE\n"
            "M109 R210 ; wait\n"
            "M109 S215\n"
        )
        self.assertTrue(changed)
        self.assertEqual(
            result,
            "M109 S200 ; heat\n"
            ";LAYER_CHANGE\n"
            "M104 S210 ; wait\n"
            "M104 S215\n",
        )

    def test_travel_swap_without_temperature_conversion(self):
        changed, result = _run(
            "T0\nG0 Z1 F100\nG0 X1\n;LAYER_CHANGE\nM109 S180\n",
            convert_m109=False,
        )
        self.assertTrue(changed)
        self.assertEqual(result, "T0\nG0 X1 F100\nG0 Z1\n;LAYER_CHANGE\nM109 S180\n")

    def test_temperature_conversion_without_travel_swap(self):
        changed, result = _run(
            "T0\nG0 Z1 F100\nG0 X1\n;LAYER_CHANGE\nM109 S180\n",
            swap_toolchange_travel=False,
        )
        self.assertTrue(changed)
        self.assertEqual(
            result,
            "T0\nG0 Z1 F100\nG0 X1\n;LAYER_CHANGE\nM104 S180\n",
        )

    def test_both_flags_off_leaves_the_file_unchanged(self):
        source = "T0\nG0 Z1 F100\nG0 X1\n;LAYER_CHANGE\nM109 S180\n"
        changed, result = _run(source, swap_toolchange_travel=False, convert_m109=False)
        self.assertFalse(changed)
        self.assertEqual(result, source)

    def test_second_pass_does_not_swap_again(self):
        source = "T0\nG0 Z1 F100\nG0 X2 Y3\n;LAYER_CHANGE\nM109 R190\n"
        _, once = _run(source)
        changed, twice = _run(once)
        self.assertFalse(changed)
        self.assertEqual(twice, once)


if __name__ == "__main__":
    unittest.main()
