#    Copyright 2020 Division of Medical Image Computing, German Cancer Research Center (DKFZ), Heidelberg, Germany
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from nnunet.paths import *
from nnunet_ext.paths import *
import nnunet, shutil, os, sys
from collections import OrderedDict
from nnunet_ext.experiment_planning.utils import no_crop
from batchgenerators.utilities.file_and_folder_operations import *
from nnunet.training.model_restore import recursive_find_python_class
from nnunet.experiment_planning.DatasetAnalyzer import DatasetAnalyzer
from nnunet.preprocessing.sanity_checks import verify_dataset_integrity
from nnunet.utilities.task_name_id_conversion import convert_id_to_task_name
from nnunet.experiment_planning.nnUNet_plan_and_preprocess import main as nnunet_main
    
def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--task_ids", nargs="+", help="List of integers belonging to the task ids you wish to run"
                                                            " experiment planning and preprocessing for. Each of these "
                                                            "ids must, have a matching folder 'TaskXXX_' in the raw "
                                                            "data folder")
    parser.add_argument("--reg", required=False, default=False, action="store_true",
                        help="Set this flag if the Lifelong nnUNet is used for registration, if so, "+
                              "no pp, no augmentation and no cropping is performed.")
    parser.add_argument("-pl3d", "--planner3d", type=str, default="ExperimentPlanner3D_v21",
                        help="Name of the ExperimentPlanner class for the full resolution 3D U-Net and U-Net cascade. "
                             "Default is ExperimentPlanner3D_v21. Can be 'None', in which case these U-Nets will not be "
                             "configured")
    parser.add_argument("-pl2d", "--planner2d", type=str, default="ExperimentPlanner2D_v21",
                        help="Name of the ExperimentPlanner class for the 2D U-Net. Default is ExperimentPlanner2D_v21. "
                             "Can be 'None', in which case this U-Net will not be configured")
    parser.add_argument("-no_pp", action="store_true",
                        help="Set this flag if you dont want to run the preprocessing. If this is set then this script "
                             "will only run the experiment planning and create the plans file")
    parser.add_argument("-tl", type=int, required=False, default=8,
                        help="Number of processes used for preprocessing the low resolution data for the 3D low "
                             "resolution U-Net. This can be larger than -tf. Don't overdo it or you will run out of "
                             "RAM")
    parser.add_argument("-tf", type=int, required=False, default=8,
                        help="Number of processes used for preprocessing the full resolution data of the 2D U-Net and "
                             "3D U-Net. Don't overdo it or you will run out of RAM")
    parser.add_argument("--verify_dataset_integrity", required=False, default=False, action="store_true",
                        help="set this flag to check the dataset integrity. This is useful and should be done once for "
                             "each dataset!")
    parser.add_argument("-overwrite_plans", type=str, default=None, required=False,
                        help="Use this to specify a plans file that should be used instead of whatever nnU-Net would "
                             "configure automatically. This will overwrite everything: intensity normalization, "
                             "network architecture, target spacing etc. Using this is useful for using pretrained "
                             "model weights as this will guarantee that the network architecture on the target "
                             "dataset is the same as on the source dataset and the weights can therefore be transferred.\n"
                             "Pro tip: If you want to pretrain on Hepaticvessel and apply the result to LiTS then use "
                             "the LiTS plans to run the preprocessing of the HepaticVessel task.\n"
                             "Make sure to only use plans files that were "
                             "generated with the same number of modalities as the target dataset (LiTS -> BCV or "
                             "LiTS -> Task008_HepaticVessel is OK. BraTS -> LiTS is not (BraTS has 4 input modalities, "
                             "LiTS has just one)). Also only do things that make sense. This functionality is beta with"
                             "no support given.\n"
                             "Note that this will first print the old plans (which are going to be overwritten) and "
                             "then the new ones (provided that -no_pp was NOT set).")
    parser.add_argument("-overwrite_plans_identifier", type=str, default=None, required=False,
                        help="If you set overwrite_plans you need to provide a unique identifier so that nnUNet knows "
                             "where to look for the correct plans and data. Assume your identifier is called "
                             "IDENTIFIER, the correct training command would be:\n"
                             "'nnUNet_train CONFIG TRAINER TASKID FOLD -p nnUNetPlans_pretrained_IDENTIFIER "
                             "-pretrained_weights FILENAME'")

    args = parser.parse_args()
    if args.reg:
        # -- Do planning etc for registration -- #
        # -- Copied from original implementation and modified accordingly -- #
        task_ids = args.task_ids
        tl = args.tl
        tf = args.tf
        planner_name3d = args.planner3d
        planner_name2d = args.planner2d
        dont_run_preprocessing = args.no_pp
        
        if planner_name3d == "None":
            planner_name3d = None
        if planner_name2d == "None":
            planner_name2d = None
            
        if args.overwrite_plans is not None:
            if planner_name2d is not None:
                print("Overwriting plans only works for the 3d planner. I am setting '--planner2d' to None. This will "
                    "skip 2d planning and preprocessing.")
            assert planner_name3d == 'ExperimentPlanner3D_v21_Pretrained', "When using --overwrite_plans you need to use " \
                                                                        "'-pl3d ExperimentPlanner3D_v21_Pretrained'"

        tasks = []
        for i in task_ids:
            i = int(i)

            task_name = convert_id_to_task_name(i)

            if args.verify_dataset_integrity:
                verify_dataset_integrity(join(nnUNet_raw_data, task_name))

            # -- No cropping here as we can not crop data for registration, should all have the same shape -- #
            dims = no_crop(task_name, False, tf)
            
            tasks.append(task_name)

        search_in = join(nnunet.__path__[0], "experiment_planning")

        if planner_name3d is not None:
            planner_3d = recursive_find_python_class([search_in], planner_name3d, current_module="nnunet.experiment_planning")
            if planner_3d is None:
                raise RuntimeError("Could not find the Planner class %s. Make sure it is located somewhere in "
                                   "nnunet.experiment_planning" % planner_name3d)
        else:
            planner_3d = None

        if planner_name2d is not None:
            planner_2d = recursive_find_python_class([search_in], planner_name2d, current_module="nnunet.experiment_planning")
            if planner_2d is None:
                raise RuntimeError("Could not find the Planner class %s. Make sure it is located somewhere in "
                                "nnunet.experiment_planning" % planner_name2d)
        else:
            planner_2d = None

        for t in tasks:
            print("\n\n\n", t)
            cropped_out_dir = os.path.join(nnUNet_cropped_data, t)
            preprocessing_output_dir_this_task = os.path.join(preprocessing_output_dir, t)

            # we need to figure out if we need the intensity propoerties. We collect them only if one of the modalities is CT
            dataset_json = load_json(join(cropped_out_dir, 'dataset.json'))
            modalities = list(dataset_json["modality"].values())
            collect_intensityproperties = True if (("CT" in modalities) or ("ct" in modalities)) else False
            dataset_analyzer = DatasetAnalyzer(cropped_out_dir, overwrite=False, num_processes=tf)  # this class creates the fingerprint
            _ = dataset_analyzer.analyze_dataset(collect_intensityproperties)  # this will write output files that will be used by the ExperimentPlanner


            maybe_mkdir_p(preprocessing_output_dir_this_task)
            shutil.copy(join(cropped_out_dir, "dataset_properties.pkl"), preprocessing_output_dir_this_task)
            shutil.copy(join(nnUNet_raw_data, t, "dataset.json"), preprocessing_output_dir_this_task)

            threads = (tl, tf)
            
            # -- Build noNorm schemes -- #
            schemes, norms = OrderedDict(), OrderedDict()
            for i in range(dims-1):
                schemes[i] = 'noNorm'
                norms[i] = False
                
            print("number of threads: ", threads, "\n")

            if planner_3d is not None:
                if args.overwrite_plans is not None:
                    assert args.overwrite_plans_identifier is not None, "You need to specify -overwrite_plans_identifier"
                    exp_planner = planner_3d(cropped_out_dir, preprocessing_output_dir_this_task, args.overwrite_plans,
                                            args.overwrite_plans_identifier)
                else:
                    exp_planner = planner_3d(cropped_out_dir, preprocessing_output_dir_this_task)
                exp_planner.plan_experiment()
                # -- Manually change normalization_schemes to noNorm -- #
                exp_planner.plans['normalization_schemes'], exp_planner.plans['use_mask_for_norm'] = schemes, norms
                exp_planner.save_my_plans()
            
                if not dont_run_preprocessing:  # double negative, yooo
                    exp_planner.run_preprocessing(threads)
            if planner_2d is not None:
                exp_planner = planner_2d(cropped_out_dir, preprocessing_output_dir_this_task)
                exp_planner.plan_experiment()
                # -- Manually change normalization_schemes to noNorm -- #
                exp_planner.plans['normalization_schemes'], exp_planner.plans['use_mask_for_norm'] = schemes, norms
                exp_planner.save_my_plans()
                if not dont_run_preprocessing:  # double negative, yooo
                    exp_planner.run_preprocessing(threads)
        # -- Copied from original implementation and modified accordingly -- #
    else:
        # -- Keep as is from nnUNet, as we don't want to change anything here -- #
        sys.argv = args
        nnunet_main()

if __name__ == "__main__":
    main()