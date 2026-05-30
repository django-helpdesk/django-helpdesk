# Vendor

This location holds the static dependencies like bootstrap or jquery.  We now auto add these files using yarn.

```
# step 1 - download dependencies
yarn install

# step 2 - Move dependencies
yarn build:static
# or
make static-vendor

# step 3 - Run project
make rundemo

# step 4 - clean up
make distclean

```
Note: The following libs are not currently in yarn
* flot
* flot-tooltip
* morisjs
* timeline3
