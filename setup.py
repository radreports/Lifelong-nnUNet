#########################################################################################################
#--------------------------Corresponding setup.py file for nnUNet extensions.---------------------------#
#########################################################################################################

# Includes parts from original nnunet (https://github.com/MIC-DKFZ/nnUNet)
import pathlib
from setuptools import setup, find_namespace_packages


# -- The directory containing this file] -- #
HERE = pathlib.Path(__file__).parent

# -- The text of the README file -- #
README = (HERE / "README.md").read_text()

# -- Setup -- #
setup(name='nnunet_ext',
      packages=find_namespace_packages(include=["nnunet_ext", "nnunet_ext.*"]),
      #version='1.6.6',
      description='Add short description',
      long_description=README,
      long_description_content_type="text/markdown",
      url='Add url',    # url to repository
      author='Add author',
      author_email='Add email address',
      license='Apache License Version 2.0, January 2004',
      install_requires=[
	tqdm
            # Add only the packages that are not in the nnUNet repositories setup.py file!
      ],
      entry_points={
          'console_scripts': [
              'nnUNet_dataset_label_mapping = nnunet_ext.experiment_planning.dataset_label_mapping:main',# Use when the labels of the masks need to be changed based on a mapping file
          ],
      },
      keywords=['deep learning', 'image segmentation', 'medical image analysis',
                'medical image segmentation', 'nnU-Net', 'nnunet', 'CL', 'Continual Learning',
                'Elastic Weight Consolidation', 'Learning Without Forgetting', 'nnU-Net extensions']
      )