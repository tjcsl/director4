from ...test.director_test import DirectorTestCase
from ..balancer import (
    BalancerProtocolError,
    balancer_open_http_request,
    get_balancer_addr,
    iter_pingable_balancers,
    ping_balancer,
)


class UtilsBalancerTestCase(DirectorTestCase):
    def test_get_balancer_addr(self):
        self.assertEqual("director-balancer1:8000", get_balancer_addr("director-balancer1:8000"))

        with self.settings(
            DIRECTOR_NUM_BALANCERS=1, DIRECTOR_BALANCER_HOSTS=["director-balancer1:8000"]
        ):
            self.assertEqual("director-balancer1:8000", get_balancer_addr(-1, allow_random=True))
            self.assertEqual("director-balancer1:8000", get_balancer_addr(0))

            with self.assertRaises(ValueError):
                self.assertEqual(
                    "director-balancer1:8000", get_balancer_addr(-1, allow_random=False)
                )

    # Figure out some better way to test this.
    def test_balancer_open_http_request(self):
        with self.assertRaises(BalancerProtocolError):
            balancer_open_http_request("director-balancertest:8000", path="/test", timeout=1)

    def test_ping_balancer(self):
        self.assertFalse(ping_balancer("director-balancertest:8000", timeout=1))

    def test_iter_pingable_balancers(self):
        with self.settings(
            DIRECTOR_NUM_BALANCERS=2,
            DIRECTOR_BALANCER_HOSTS=["director-balancertest1:8000", "director-balancertest2:8000"],
        ):
            for result in iter_pingable_balancers(timeout=1):
                self.assertFalse(result)
