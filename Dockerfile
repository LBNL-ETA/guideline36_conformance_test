FROM openmodelica/openmodelica:v1.25.0-ompython

COPY requirements.txt ./requirements.txt

# Install conda from docker image
COPY --from=continuumio/miniconda3:25.3.1-1 /opt/conda /opt/conda

ENV PATH=/opt/conda/bin:$PATH

# Install python packages using conda
RUN set -ex && \
    conda config --set always_yes yes --set changeps1 no && \
    conda info -a && \
    conda config --add channels conda-forge && \
    conda install --quiet --freeze-installed -c main conda-pack

RUN conda install --file requirements.txt

ENV PYTHONPATH=/mnt/shared