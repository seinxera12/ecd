import unittest

from ECD.dxf_generator import ensure_connections


class DxfTopologyTests(unittest.TestCase):
    def test_branching_connections_are_created_deterministically(self):
        parsed_data = {
            "components": [
                ("supply", "Supply"),
                ("maincb", "Main Breaker"),
                ("rcd", "RCD"),
                ("bus", "Busbar"),
                ("outcb_1", "Lighting CB"),
                ("outcb_2", "Socket CB"),
                ("loads", "Loads"),
            ]
        }

        connections = ensure_connections(parsed_data)

        self.assertEqual(
            connections,
            [
                ("supply", "maincb"),
                ("maincb", "rcd"),
                ("rcd", "bus"),
                ("bus", "outcb_1"),
                ("bus", "outcb_2"),
                ("outcb_1", "loads"),
                ("outcb_2", "loads"),
            ],
        )



if __name__ == "__main__":
    unittest.main()
