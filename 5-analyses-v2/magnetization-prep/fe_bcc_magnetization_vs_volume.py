import numpy as np

from aiida.plugins import WorkflowFactory
from aiida import orm, load_profile
from aiida.engine import submit
from aiida_common_workflows.common import ElectronicType, RelaxType, SpinType
from aiida_common_workflows.plugins import get_entry_point_name_from_class
from aiida_common_workflows.plugins import load_workflow_entry_point

load_profile()


fe_bcc_query = orm.QueryBuilder().append(
    orm.StructureData, 
    filters={'and': [{'extras.element': 'Fe'}, {'extras.configuration': 'X/BCC'}]}, 
    project='*'
)

if fe_bcc_query.count() > 1:
    raise ValueError("More than one Fe BCC structure found.")

fe_bcc_structure = fe_bcc_query.all(flat=True)[0]

# Define scale factors
scale_factors = np.round(
    np.concatenate(
        [
            np.arange(0.4, 0.5, 0.04),
            np.arange(0.5, 0.64, 0.01),
            np.arange(0.64, 1.1, 0.04),
            np.arange(1.1, 1.3, 0.01),
            np.arange(1.3, 1.65, 0.04),
        ]
    ), 3
).tolist()


################################
### Plugin specific inputs
################################
PLUGIN_NAME = ...
CODE_LABEL = ...
engine_options = ...
sub_process_overrides = ...

##########
# Example for QE
##########

# # PLUGIN_NAME = 'quantum_espresso'


# # if PLUGIN_NAME == 'quantum_espresso':
# #     CODE_LABEL = 'qe-7.3-gf-pw@thor'
# #     engine_options = {
# #         'code': CODE_LABEL,
# #         'options': {
# #             'resources': {
# #                 'num_machines': 1,
# #                 'num_mpiprocs_per_machine': 48
# #             },
# #             'queue_name': 'lms',
# #             'max_wallclock_seconds': 1 * 3600,
# #         }
# #     }
    
# #     sub_process_overrides = {  # optional code-dependent overrides
# #         'clean_workdir': orm.Bool(True),
# #         'base': {
# #             'pw': {
# #                 'settings' : orm.Dict(dict= {
# #                     'cmdline': ['-nk', '8'],
# #                 })
# #             }
# #         },
# #         'base_final_scf': {
# #             'pw': {
# #                 'settings' : orm.Dict(dict= {
# #                     'cmdline': ['-nk', '8'],
# #                 })
# #             }
# #         },
# #     }

eos_wc = WorkflowFactory('common_workflows.eos')

sub_process_cls = load_workflow_entry_point('relax', PLUGIN_NAME)
sub_process_cls_name = get_entry_point_name_from_class(sub_process_cls).name
generator = sub_process_cls.get_input_generator()

engine_types = generator.spec().inputs['engines']
engines = {}

for engine in engine_types:
    engines[engine] = engine_options

inputs = {
    'structure': fe_bcc_structure,
    'scale_factors': orm.List(scale_factors),
    'generator_inputs': {  # code-agnostic inputs for the relaxation
        'engines': engines,
        'protocol': 'verification-PBE-v1',
        'relax_type': RelaxType.NONE,
        'electronic_type': ElectronicType.METAL,
        'spin_type': SpinType.COLLINEAR,
        'magnetization_per_site': [3]
    },
    'sub_process_class': sub_process_cls_name,
    'sub_process' : sub_process_overrides
}

wc_node = submit(eos_wc, **inputs)

print(f"Submitted EOS WorkChain with pk {wc_node.pk}")
