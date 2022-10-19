
from python:3.6
RUN pip install --upgrade pip && pip install \
  prompt-toolkit==3.0.29 \
   \
  pygments
RUN mkdir /xonsh
WORKDIR /xonsh
ADD ./ ./
RUN python setup.py install
