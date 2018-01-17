# RowGroup

RowGroup adds the ability to easily group rows in a DataTable by a given data point. The grouping is shown as an inserted row either before or after the group.

It is worth nothing that RowGroup currently does not work with:

* The Scroller extension for DataTables
* Export buttons for DataTables (the data will be shown, but the grouping is not).


# Installation

To use RowGroup the primary way to obtain the software is to use the [DataTables downloader](//datatables.net/download). You can also include the individual files from the [DataTables CDN](//cdn.datatables.net). See the [documentation](http://datatables.net/extensions/rowgroup/) for full details.

## NPM and Bower

If you prefer to use a package manager such as NPM or Bower, distribution repositories are available with software built from this repository under the name `datatables.net-rowgroup`. Styling packages for Bootstrap, Foundation and other styling libraries are also available by adding a suffix to the package name.

Please see the DataTables [NPM](//datatables.net/download/npm) and [Bower](//datatables.net/download/bower) installation pages for further information. The [DataTables installation manual](//datatables.net/manual/installation) also has details on how to use package managers with DataTables.


# Basic usage

RowGroup is initialised using the `rowGroup` option in the DataTables constructor - a simple boolean `true` will enable the feature, but you will most likely wish to use the `rowGroup.dataSrc` option to configure the data parameter which should be used to read the grouping data from.

Example:

```js
$(document).ready( function () {
    $('#myTable').DataTable( {
    	rowGroup: {
            dataSrc: 0
        }
    } );
} );
```


# Documentation / support

* [Documentation](https://datatables.net/extensions/rowgroup/)
* [DataTables support forums](http://datatables.net/forums)


# GitHub

If you fancy getting involved with the development of RowGroup and help make it better, please refer to its [GitHub repo](https://github.com/DataTables/RowGroup).

