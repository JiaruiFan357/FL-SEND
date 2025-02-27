# FL-SEND-PSE

FL-SEND-PSE is a research project developed in 2025 at Leibniz University Hannover, Germany. It focuses on enhancing speaker diarization—the process of determining "who spoke when" in audio recordings—by integrating Power-Set Encoding (PSE) within a Federated Learning (FL) framework. This approach aims to improve the handling of overlapping speech segments while preserving data privacy.

## Introduction

Speaker diarization is essential for applications like meeting transcription and conversational AI. Traditional methods often struggle with overlapping speech, leading to inaccuracies. FL-SEND-PSE aims to combine Power-Set Encoding with Federated Learning, enabling effective modeling of overlapping speech without compromising user privacy.

## Repository Structure

- `Callhome_Preprocess.ipynb`: Notebook for preprocessing the CALLHOME dataset, including extraction and simulation of overlapping speech segments, resulting in a `.pkl` file.
- `SEND_PSE_AMI5000.ipynb` and `SEND_PSE_AMI10000.ipynb`: Notebooks for training the SEND-PSE model on subsets of the AMI dataset.
- `SEND_PSE_Callhome.ipynb`: Notebook for training the SEND-PSE model on the CALLHOME dataset.
- `FL_SEND_+_PSE_Callhome.ipynb`: Notebook for federated training of the FL-SEND-PSE model using the CALLHOME dataset.
- `preprocessed_callhome_data.pkl`: Preprocessed CALLHOME dataset file generated by `Callhome_Preprocess.ipynb`.
- `requirements.txt`: List of required Python packages.

## Datasets

- **CALLHOME Dataset** (available at [Hugging Face](https://huggingface.co/datasets/talkbank/callhome))
- **AMI Meeting Corpus** (available at [Hugging Face](https://huggingface.co/datasets/edinburghcstr/ami))

## Usage

### Preprocessing the CALLHOME Dataset

Before training, preprocess the CALLHOME dataset to extract and simulate overlapping speech segments:

1. Download the CALLHOME dataset and place it in the appropriate directory.
2. Open and run the `Callhome_Preprocess.ipynb` notebook to generate the `preprocessed_callhome_data.pkl` file.

### Training the SEND-PSE Model

To train the Speaker Embedding-aware Neural Diarization model with Power-Set Encoding:

1. Choose the appropriate dataset notebook (`SEND_PSE_AMI5000.ipynb`, `SEND_PSE_AMI10000.ipynb`, or `SEND_PSE_Callhome.ipynb`).
2. Open and run the selected notebook to train the model on the desired dataset.

### Federated Training with FL-SEND-PSE

For federated learning using the FL-SEND-PSE model:

1. Ensure that the preprocessed CALLHOME data (`preprocessed_callhome_data.pkl`) is available.
2. Open and run the `FL_SEND_+_PSE_Callhome.ipynb` notebook to initiate federated training across simulated clients.

## Requirements

All required Python packages are listed in the `requirements.txt` file. Install them using the provided installation command.

## Device Compatibility

The notebooks are initally developed and compiled with the following devices, when run it, please make srue to change device to your desired one in the code:

- **CPU**: For general computation.
- **CUDA**: For NVIDIA GPUs. Ensure that the CUDA toolkit is installed and properly configured.
- **MPS**: For Apple Silicon devices.

