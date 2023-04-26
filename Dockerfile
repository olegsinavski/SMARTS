FROM mlgl_sandbox

COPY utils/setup/install_deps.sh /root/install_deps.sh
RUN chmod +x /root/install_deps.sh
RUN /root/install_deps.sh

COPY --chown=docker:docker . /home/docker/smarts

USER docker
WORKDIR /home/docker/
ENV VIRTUAL_ENV=/home/docker/venv
RUN python3.8 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# https://github.com/openai/gym/issues/3202
RUN pip install wheel==0.38.4 setuptools==65.5.1
WORKDIR /home/docker/smarts
RUN pip install -e '.[camera_obs,test,train,diagnostic]'
# RUN make sanity-test

RUN echo "source venv/bin/activate" >> ~/.bashrc

USER root