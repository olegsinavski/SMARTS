FROM mlgl_sandbox

COPY utils/setup/install_deps.sh /root/install_deps.sh
RUN chmod +x /root/install_deps.sh
RUN /root/install_deps.sh

COPY --chown=docker:docker . /home/docker/smarts

USER docker
WORKDIR /home/docker/smarts
ENV VIRTUAL_ENV=/home/docker/smarts/venv
RUN python3.8 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"


# https://github.com/openai/gym/issues/3202
RUN pip install wheel==0.38.4 setuptools==65.5.1
RUN pip install -e '.[camera_obs,test,train]'
RUN make sanity-test

RUN echo "cd smarts && source venv/bin/activate" >> ~/.bashrc

USER root