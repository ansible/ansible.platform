"""Integration tests: run Molecule scenarios via pytest-ansible (tox-ansible integration env)."""

from __future__ import absolute_import, division, print_function

from pytest_ansible.molecule import MoleculeScenario


def test_molecule_scenario(molecule_scenario: MoleculeScenario) -> None:
    """Run each Molecule scenario (e.g. extensions/molecule/users).

    Discovered from extensions/molecule/*/molecule.yml; each scenario runs
    molecule test -s <scenario_name> so converge, verify, and cleanup run.
    """
    proc = molecule_scenario.test()
    assert proc.returncode == 0, f"molecule test failed for scenario {molecule_scenario.name!r}: returncode={proc.returncode}"
