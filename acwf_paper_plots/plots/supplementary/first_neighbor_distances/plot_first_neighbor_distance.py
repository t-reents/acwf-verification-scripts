#!/usr/bin/env python
import json
import os
import sys
from collections import defaultdict
from copy import deepcopy

from ase.data import chemical_symbols, atomic_numbers
import numpy as np
import pylab as pl
from matplotlib.ticker import MultipleLocator, FormatStrFormatter

Z_max = 103
Pettifor_max = 103

# Precompute Pettifor values
from pymatgen.core.periodic_table import Element
pettifor_scale = {}
# I can create the Pettifor 
for Z in range(1, Pettifor_max + 1):
    pettifor = int(Element(chemical_symbols[Z]).mendeleev_no)
    pettifor_scale[chemical_symbols[Z]] = pettifor
assert len(pettifor_scale.values()) == len(set(pettifor_scale.values())), "Duplicate Pettifor values found!"

# Generate also reverse table, 
inverse_pettifor_to_Z = [None] * (max(pettifor_scale.values()) + 1)
for symbol, pettifor in pettifor_scale.items():
    inverse_pettifor_to_Z[pettifor] = atomic_numbers[symbol]


alat_to_first_neighbor_factor = {
    'SC': 1.,
    'FCC': np.sqrt(2)/2,
    'BCC': np.sqrt(3)/2,
    'Diamond': np.sqrt(3)/4,
    'XO': 1/2,
    'X2O': np.sqrt(3)/4,
    'XO3': 1/2,
    'XO2': np.sqrt(3)/4,
    'X2O3': np.sqrt(3)/4,
    'X2O5': np.sqrt(3)/4
}

MARKERS = {
    'SC': 's',
    'FCC': 'o',
    'BCC': 'X',
    'Diamond': '^',
    'XO': 's',
    'X2O': 'o',
    'XO3': 'X',
    'XO2': '^',
    'X2O3': 'D',
    'X2O5': 'P',
}
# Essentially, how many atoms there are in the conventional cube
volume_per_atom_to_cubic_volume = {
    'SC': 1.,
    'BCC': 2.,
    'FCC': 4.,
    'Diamond': 8.,
    'X2O': 12,
    'XO': 8,
    'XO2': 12,
    'X2O3': 10,
    'X2O5': 14,
    'XO3': 4,
}

def get_alat_from_raw_json(json_data):
    assert json_data['script_version'] in ["0.0.3", "0.0.4"]

    data = defaultdict(dict)

    for key, values in json_data['BM_fit_data'].items():
        element, config = key.split('-')
        if config.startswith('X/'):
            config = config[len('X/'):]
        
        # if key not in json_data['num_atoms_in_sim_cell']:
        #     continue

        if values is None:
            data[config][element] = None
        else:
            volume = values['min_volume']
            # num_atoms_in_sim_cell = json_data['num_atoms_in_sim_cell'][key]
            num_atoms_in_sim_cell = 2 if 'Diamond' in config else 1
            if key in json_data['num_atoms_in_sim_cell']:
                assert json_data['num_atoms_in_sim_cell'][key] == num_atoms_in_sim_cell
            volume_per_atom = volume / num_atoms_in_sim_cell
            cubic_volume = volume_per_atom * volume_per_atom_to_cubic_volume[config]
            data[config][element] = cubic_volume ** (1/3)

    return dict(data)

def generate_plots(fleur_alats, wien2k_alats, plot_vs_pettifor=False):

    # We compute the average between fleur and wien2k
    # First, check that there are all the same configurations and elements
    assert fleur_alats.keys() == wien2k_alats.keys()
    for key in fleur_alats:
        assert fleur_alats[key].keys() == wien2k_alats[key].keys()
    # Now we generate the average, and do some double checks
    average_alats = defaultdict(dict)
    for config in fleur_alats:
        for element in fleur_alats[config]:
            fleur = fleur_alats[config][element]
            wien2k = wien2k_alats[config][element]
            if fleur is None or wien2k is None:
                average_alats[config][element] = None
            else:
                average_alats[config][element] = (fleur + wien2k) / 2
                assert abs((fleur - wien2k) / wien2k) < 0.01, f"Data for {element}-{config} has large error: {fleur} {wien2k} {abs((fleur - wien2k) / wien2k)}!"
                assert abs((fleur - wien2k) / wien2k) > 1.e-14, f"Data for {element}-{config} seem to be really identical! Maybe a copy-paste error?"

    if 'Diamond' in average_alats:
        set_type = 'unaries'
        valid_configurations = ['SC', 'BCC', 'FCC', 'Diamond'] # I hardcode them here to have a given order
    elif 'X2O5' in average_alats:
        set_type = 'oxides'
        valid_configurations = ['X2O', 'XO', 'X2O3', 'XO2', 'X2O5', 'XO3'] # I hardcode them here to have a given order
    else:
        raise ValueError("Unknown set!")
    assert set(valid_configurations) == set(average_alats.keys())

    if plot_vs_pettifor:
        pettifor_values = [True, False]
    else:
        pettifor_values = [False]
    for plot_vs_pettifor in pettifor_values:
        fig, ax = pl.subplots(figsize=(9, 3))
        pl.subplots_adjust(left=0.07, right=0.99, bottom=0.15)
        if plot_vs_pettifor:
            pl.xlabel("Mendeleev's number")
            x = np.arange(1, max(pettifor_scale.values()) + 1)
        else:
            pl.xlabel("Atomic number $Z$")
            x = np.arange(1, Z_max + 1)
            y = np.zeros(len(x))
            for conf in valid_configurations: # I use this dictionary so they are in the order I want
                for idx in range(len(x)):
                    if plot_vs_pettifor:
                        pettifor = x[idx]
                        Z = inverse_pettifor_to_Z[pettifor]
                    else:
                        Z = x[idx]

                    # In case Z is None, I pre-set to None so the point is not plotted
                    first_neighbor = None
                    if Z <= Z_max:
                        if average_alats[conf].get(chemical_symbols[Z], None) is None:
                            print(f"WARNING: MISSING {chemical_symbols[Z]} -> {conf}")
                        else:
                            # alat * factor
                            first_neighbor = average_alats[conf][chemical_symbols[Z]] * alat_to_first_neighbor_factor[conf]
                    else:
                        print(idx, Z, 'SKIP')
                    y[idx] = first_neighbor

                marker = MARKERS[conf]

                latex_conf = "".join([f"$_{char}$" if char in "0123456789" else char for char in conf])
                pl.plot(x, y, f'{marker}-', markersize=3, linewidth=1, label=f'{latex_conf}')

            pl.ylabel("First-neighbor distance (Å)")

            from matplotlib.ticker import (MultipleLocator, FormatStrFormatter,
                                        AutoMinorLocator)

            ax.xaxis.set_major_locator(MultipleLocator(10))
            ax.minorticks_on()
            ax.xaxis.set_minor_locator(MultipleLocator(1))
            pl.grid(which='major', axis='x', color='#ccc', linestyle='-')
            pl.grid(which='minor', axis='x', color='#eee', linestyle='-')
            pl.xlim(1,x.max())

            pl.grid(which='major', axis='y', color='#ccc', linestyle='-')
            pl.grid(which='minor', axis='y', color='#eee', linestyle='dotted')

            sec = ax.secondary_xaxis(location='top')
            if plot_vs_pettifor:
                ticks_x = np.arange(1, max(pettifor_scale.values()) + 1)
                sec.set_xticks(ticks_x)
                sec.set_xticklabels([chemical_symbols[inverse_pettifor_to_Z[pettifor]] for pettifor in ticks_x])
            else:
                ticks_x = np.arange(1, Z_max+1)
                sec.set_xticks(ticks_x)
                sec.set_xticklabels([chemical_symbols[Z] for Z in ticks_x], fontsize=7)

            sec.tick_params(rotation=90)

            if plot_vs_pettifor:
                pl.legend(loc='upper right', ncol=2)
            else:
                if set_type == 'oxides':
                    pl.ylim(1.4, 3.7)
                    pl.legend(loc='lower right', ncol=6)
                else:
                    pl.ylim(1, 5.8)
                    pl.legend(loc='lower right', ncol=4)

        fname_suffix = "-vs_mendeleev.pdf" if plot_vs_pettifor else ""
        fname = f'first-neighbor-distance-{set_type}{fname_suffix}.pdf'
        pl.savefig(fname)
        print(f"'{fname}' written.")

def generate_subplots(data_dict, plot_vs_pettifor=False):
    """
    Generate subplots for each structural configuration and plot the results of different functionals.
    
    :param data_dict: Dictionary containing data for different functionals.
                      Format: {functional_name: {config: {element: value}}}
    :param plot_vs_pettifor: Boolean to decide whether to plot against Pettifor scale or atomic number.
    """
    # Check that all functionals have the same configurations and elements
    functionals = list(data_dict.keys())
    assert all(data_dict[func].keys() == data_dict[functionals[0]].keys() for func in functionals)
    # for config in data_dict[functionals[0]]:
    #     assert all(data_dict[func][config].keys() == data_dict[functionals[0]][config].keys() for func in functionals)

    valid_configurations = list(data_dict[functionals[0]].keys())

    if plot_vs_pettifor:
        pettifor_values = [True, False]
    else:
        pettifor_values = [False]
    for plot_vs_pettifor in pettifor_values:
        fig, axs = pl.subplots(len(valid_configurations), 1, figsize=(9, 3 * len(valid_configurations)))
        pl.subplots_adjust(left=0.07, right=0.99, bottom=0.05, top=0.95, hspace=0.5)
        if plot_vs_pettifor:
            x = np.arange(1, max(pettifor_scale.values()) + 1)
        else:
            x = np.arange(1, Z_max + 1)

        for i, conf in enumerate(valid_configurations):
            ax = axs[i]
            if plot_vs_pettifor:
                ax.set_xlabel("Mendeleev's number")
            else:
                ax.set_xlabel("Atomic number $Z$")
            y = np.zeros(len(x))
            for func in functionals:
                for idx in range(len(x)):
                    if plot_vs_pettifor:
                        pettifor = x[idx]
                        Z = inverse_pettifor_to_Z[pettifor]
                    else:
                        Z = x[idx]

                    first_neighbor = None
                    if Z <= Z_max:
                        if data_dict[func][conf].get(chemical_symbols[Z], None) is None:
                            print(f"WARNING: MISSING {chemical_symbols[Z]} -> {conf} for {func}")
                        else:
                            first_neighbor = data_dict[func][conf][chemical_symbols[Z]] * alat_to_first_neighbor_factor[conf]
                    y[idx] = first_neighbor

                marker = MARKERS[conf]
                latex_conf = "".join([f"$_{char}$" if char in "0123456789" else char for char in conf])
                ax.plot(x, y, f'{marker}-', markersize=3, linewidth=1, label=f'{func}', alpha=0.5)
                ax.set_title(f'{latex_conf}')
            ax.set_ylabel("First-neighbor distance (Å)")
            ax.xaxis.set_major_locator(MultipleLocator(10))
            ax.minorticks_on()
            ax.xaxis.set_minor_locator(MultipleLocator(1))
            ax.grid(which='major', axis='x', color='#ccc', linestyle='-')
            ax.grid(which='minor', axis='x', color='#eee', linestyle='-')
            ax.grid(which='major', axis='y', color='#ccc', linestyle='-')
            ax.grid(which='minor', axis='y', color='#eee', linestyle='dotted')
            ax.set_xlim(1, x.max())

            sec = ax.secondary_xaxis(location='top')
            if plot_vs_pettifor:
                ticks_x = np.arange(1, max(pettifor_scale.values()) + 1)
                sec.set_xticks(ticks_x)
                sec.set_xticklabels([chemical_symbols[inverse_pettifor_to_Z[pettifor]] for pettifor in ticks_x])
            else:
                ticks_x = np.arange(1, Z_max+1)
                sec.set_xticks(ticks_x)
                sec.set_xticklabels([chemical_symbols[Z] for Z in ticks_x], fontsize=7)

            sec.tick_params(rotation=90)
            ax.legend(loc='lower right', ncol=3)

        fname_suffix = "-vs_mendeleev.pdf" if plot_vs_pettifor else ""
        fname = f'first-neighbor-distance-subplots{fname_suffix}.pdf'
        pl.savefig(fname)
        print(f"'{fname}' written.")

if __name__ == "__main__":
    try:
        set_name = sys.argv[1]
        if set_name not in ['unaries', 'oxides']:
            raise IndexError
    except IndexError:
        print("Pass either 'oxides' or 'unaries' on the command line.")
        sys.exit(2)

    DATA_FOLDER = "../../../code-data"
with open(os.path.join(DATA_FOLDER, "labels.json")) as fhandle:
    labels_data = json.load(fhandle)
    FLEUR_LABEL = labels_data['all-electron-keys']["FLEUR"]
    WIEN2k_LABEL = labels_data['all-electron-keys']["WIEN2k"]

    with open(os.path.join(DATA_FOLDER, labels_data['methods-main'][WIEN2k_LABEL][set_name])) as fhandle:
            wien2k_data = json.load(fhandle)
    with open(os.path.join(DATA_FOLDER, labels_data['methods-main'][FLEUR_LABEL][set_name])) as fhandle:
            fleur_data = json.load(fhandle)

    fleur_alats = get_alat_from_raw_json(fleur_data)
    wien2k_alats = get_alat_from_raw_json(wien2k_data)
    new_data_sub_path = '/Users/treents/project/aiida-cwf/data'

    with open(os.path.join(new_data_sub_path, 'wien2k/unaries_prec3_lda.json')) as fhandle:
        wien2k_lda_data = deepcopy(wien2k_data)
        _wien2k_lda_data = json.load(fhandle)
        wien2k_lda_data['BM_fit_data'] = _wien2k_lda_data['BM_fit_data']

    with open(os.path.join(new_data_sub_path, 'wien2k/unaries_prec3_pbesol.json')) as fhandle:
        wien2k_pbesol_data = deepcopy(wien2k_data)
        _wien2k_pbesol_data = json.load(fhandle)
        wien2k_pbesol_data['BM_fit_data'] = _wien2k_pbesol_data['BM_fit_data']
        
    with open(os.path.join(new_data_sub_path, 'wien2k/unaries_prec3_pbe.json')) as fhandle:
        wien2k_pbe_data = deepcopy(wien2k_data)
        _wien2k_pbe_data = json.load(fhandle)
        wien2k_pbe_data['BM_fit_data'] = _wien2k_pbe_data['BM_fit_data']
        
    # with open(os.path.join(new_data_sub_path, 'wien2k/oxides_prec3_pbe.json')) as fhandle:
    #     wien2k_ox_pbe_data = deepcopy(wien2k_data)
    #     _wien2k_ox_pbe_data = json.load(fhandle)
    #     wien2k_ox_pbe_data['BM_fit_data'] = _wien2k_ox_pbe_data['BM_fit_data']
        
        
    with open(
        os.path.join(new_data_sub_path, 'sirius_cp2k/LDA_v3.json')
        ) as fhandle:
        cp2k_lda_data = json.load(fhandle)
    
    with open(
        os.path.join(new_data_sub_path, 'sirius_cp2k/PBEsol_v3.json')
        ) as fhandle:
        cp2k_pbesol_data = json.load(fhandle)
        
    with open(
        os.path.join(new_data_sub_path, 'sirius_cp2k/results-unaries-verification-v1-cp2k_PBE.json')
        ) as fhandle:
        cp2k_pbe_data = json.load(fhandle)
    
    with open(
        os.path.join(new_data_sub_path, 'fleur/results-unaries-LDA-PW92-fleur_centralVolume.json')   
    ) as fhandle:
        fleur_lda_data = json.load(fhandle)
    
    wien2k_lda_alats = get_alat_from_raw_json(wien2k_lda_data)
    wien2k_pbesol_alats = get_alat_from_raw_json(wien2k_pbesol_data)
    wien2k_pbe_alats = get_alat_from_raw_json(wien2k_pbe_data)
    cp2k_lda_alats = get_alat_from_raw_json(cp2k_lda_data)
    cp2k_pbesol_alats = get_alat_from_raw_json(cp2k_pbesol_data)
    cp2k_pbe_alats = get_alat_from_raw_json(cp2k_pbe_data)
    fleur_lda_alats = get_alat_from_raw_json(fleur_lda_data)
    
    
    with open('wien2k_pbe_alats.json', 'w') as fhandle:
        json.dump(wien2k_alats, fhandle, indent=4)
    with open('wien2k_pbe_new_alats.json', 'w') as fhandle:
        json.dump(wien2k_pbe_alats, fhandle, indent=4)
    with open('wien2k_lda_alats.json', 'w') as fhandle:
        json.dump(wien2k_lda_alats, fhandle, indent=4)
    with open('wien2k_pbesol_alats.json', 'w') as fhandle:
        json.dump(wien2k_pbesol_alats, fhandle, indent=4)

    data_dict = {
        # 'FLEUR': fleur_alats,
        'PBE': wien2k_alats,
        'LDA': wien2k_lda_alats,
        'PBEsol': wien2k_pbesol_alats,
        # 'LDA-CP2K': cp2k_lda_alats
    }

    generate_plots(fleur_alats, wien2k_alats, plot_vs_pettifor=False)
    generate_subplots(data_dict, plot_vs_pettifor=False)

    
    alat_diff_data = [
        # ('FLEUR-LDA', fleur_lda_alats),
        # ('WIEN2k-PBE', wien2k_alats),
        # ('CP2K-LDA', cp2k_lda_alats),
        # ('WIEN2k-LDA', wien2k_lda_alats),
        ('CP2K-PBEsol', cp2k_pbesol_alats),
        # ('CP2K-PBE', cp2k_pbe_alats),
        ('WIEN2k-PBEsol', wien2k_pbesol_alats),
    ]
    diff_above_1perc = {}

    fig, ax = pl.subplots(ncols=4, figsize=(12, 2), sharey=True)
    pl.subplots_adjust(wspace=0.3)
    for i, config in enumerate(cp2k_lda_alats):
        rel_diff = []
        common_elements = set(
            alat_diff_data[0][1][config].keys()
        ).intersection(
            alat_diff_data[1][1][config].keys()
        )
        for element in common_elements:
            alat0 = alat_diff_data[0][1][config][element]
            alat1 = alat_diff_data[1][1][config][element]
            if alat0 is None or alat1 is None:
                continue
            rel_diff.append(
                (
                    (
                        alat0 - alat1
                        ) / alat0 * 100
                    )
            )
            if abs(rel_diff[-1]) > 1:
                diff_above_1perc.setdefault(config, {})[element] = {
                    'wien2k': alat_diff_data[0][1][config][element], 'cp2k': alat_diff_data[1][1][config][element]
                    }

            
        print(f"min, max rel diff for {config}: {min(rel_diff):.3f}\t{max(rel_diff):.3f}")
        ax[i].hist(rel_diff, bins=np.arange(-100.5, 100, 0.5), label=config)
        # ax[i].set_title(config)
        ax[i].legend()
        lab0 = alat_diff_data[0][0]
        lab1 = alat_diff_data[1][0]
        ax[i].set_xlabel("$\\frac{a_{"f"{lab0}""} - a_{"f"{lab1}""}}{a_{"f"{lab0}""}}$ (%)", fontsize=12)
        ax[i].xaxis.minorticks_on()
        ax[i].yaxis.minorticks_on()
        # ax[i].xaxis
        # ax[i].yaxis.set_minor_locator(MultipleLocator(0.1))
        ax[i].set_xlim(-5, 5)
        ax[i].xaxis.set_major_formatter(FormatStrFormatter('%d%%'))
    ax[0].set_ylabel("Occurrences")
        
    with open(f'{lab0}_{lab1}_diff_above_1perc.json', 'w') as fhandle:
        json.dump(diff_above_1perc, fhandle, indent=4)
    pl.savefig(f'histogram_{lab0}_vs_{lab1}.pdf', bbox_inches='tight')