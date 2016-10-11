if [[ $CIRCLE_NODE_INDEX == 0 ]]
then
    conda create -q -n test_env python=3.4 pygments prompt_toolkit ply pytest pytest-timeout psutil numpy matplotlib
fi


if [[ $CIRCLE_NODE_INDEX == 1 ]]
then
    conda create -q -n test_env python=3.5 pygments prompt_toolkit ply pytest pytest-timeout psutil numpy matplotlib
fi
