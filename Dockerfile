from python:3
RUN pip install --upgrade pip && pip install \
  ply \
  prompt-toolkit \
  pygments
RUN mkdir /xonsh
WORKDIR /xonsh
ADD ./ ./
RUN python setup.py install
CMD /usr/bin/env xonsh
ENV XONSH_COLOR_STYLE "paraiso-dark"
