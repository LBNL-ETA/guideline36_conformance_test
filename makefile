IMG_NAME=guideline36_conformance_test

COMMAND_RUN=docker run \
            --name mpcpy \
            --detach=false \
            --rm \
            -v `pwd`:/mnt/shared \
            -i \
            -t \
            ${IMG_NAME} /bin/bash -c

build:
	docker build --no-cache --rm -t ${IMG_NAME} .

remove-image:
	docker rmi ${IMG_NAME}

run:
	$(COMMAND_RUN) \
            "cd /mnt/shared && export PYTHONPATH=/mnt/shared && bash"