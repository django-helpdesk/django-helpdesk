/* Variables */

var key = {
    // DC Specific
    affordable_boolean: 'e_is_affordable_housing',
    property_list: 'e_property_type',
    pathway_list: 'e_pathway',
    new_pathway_list: 'e_new_pathway',
    backup_pathway_list: 'e_backup_pathway',
    attachment: 'attachment',

    // DC-staging
    extended_delay_for_QAH: 'e_extended_delay_for_QAH',
    delay_years: 'e_delay_years',
    type_affordable_housing: 'e_type_affordable_housing',
    attachment_1: 'attachment_1',
    attachment_2: 'attachment_2',
    attachment_3: 'attachment_3',

    // Ann Arbor Specific
    ext_or_exempt: 'e_extension_or_exemption',
    ext_reason: 'e_extension_reason'
};

var id = {};
var group = {};
for (let [k, v] of Object.entries(key)) {
  id[k] ='#id_' + v;
  group[k] = '#id_group_' + v;
}

var high_perf = ['Adult Education','Ambulatory Surgical Center','Multifamily Housing','Automobile Dealership','Bank Branch','Bar/Nightclub','Barracks','Courthouse','College/University','Convenience Store with Gas Station','Convenience Store without Gas Station','Financial Office','Data Center','Drinking Water Treatment & Distribution','Enclosed Mall','Office','Fast Food Restaurant','Food Sales','Food Service','Hospital (General Medical & Surgical)','Hotel','Laboratory','Lifestyle Center','Medical Office','Other - Education','Other - Lodging/Residential','Other - Mall','Other - Restaurant/Bar','Other - Specialty Hospital','Outpatient Rehabilitation/Physical Therapy','Pre-school/Daycare','Prison/Incarceration','Residence Hall/Dormitory','Residential Care Facility','Restaurant','Retail Store','Self-Storage Facility','Senior Care Community (also know as Senior Livi Community)','Strip Mall','Supermarket/Grocery Store','Urgent Care/Clinic/Other Outpatient','Veterinary Office','Vocational School','Wastewater Treatment Plant','Wholesale Club/Supercenter']

/* Alerts */
var alertMsg1 = 'This property type is not eligible for the Standard Target Pathway, please select another pathway.';
var alertMsg2 = 'You have selected the Prescriptive Pathway, please note that DOEE will not approve this selection until the building owner has submitted an energy audit. For more information please see this <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS/55/">FAQ</a>.';
var alertMsg5 = 'If selecting the ACP, you must select a Backup Pathway and attach an ACP proposal with supporting documentation as specified in <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS_Guidebook/69/">Chapter 4</a> of the <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS_Guidebook/">BEPS Guidebook</a>.'
var alertMsg6 = 'If selecting the ACP, you must attach an ACP proposal with supporting documentation as specified in <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS_Guidebook/69/">Chapter 4</a> of the <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS_Guidebook/">BEPS Guidebook</a>.'

/* This field appears if "Pathway" = "Standard Target Pathway" AND ("Primary Property Type - Portfolio Manager Calculated" NOT IN High Performance List) */
jQuery.validator.addMethod('alert1', function (value, element, param) {
    return this.optional(element) || !($(param.path).val() == 'Standard Target Pathway' && ($.inArray(value, high_perf) == -1));
}, alertMsg1);

jQuery.validator.addMethod('alert2', function (value, element) {
    var ok = this.optional(element) || value != 'Prescriptive Pathway';
    if(!ok) $(element).addClass("error-okay");
    else $(element).removeClass("error-okay");
    return ok;
}, alertMsg2);

jQuery.validator.addMethod('alert5', function (value, element) {
    var ok =  this.optional(element) || value != 'Alternative Compliance Pathway';
    if(!ok) $(element).addClass("error-okay");
    else $(element).removeClass("error-okay");
    return ok;
}, alertMsg5);

jQuery.validator.addMethod('alert6', function (value, element) {
    var ok =  this.optional(element) || value != 'Alternative Compliance Pathway';
    if(!ok) $(element).addClass("error-okay");
    else $(element).removeClass("error-okay");
    return ok;
}, alertMsg6);


/* Validations */
var form_validator = $('#ticket_submission_form').validate({
    ignore: '.error-okay',
    rules: {
        [key.pathway_list]: {
            alert2: true,
            alert5: Object.keys($(id.new_pathway_list)).length === 0,
        },
        [key.new_pathway_list]: {
            alert6: true,
        },
        [key.backup_pathway_list]: {
            alert2: true,
        },
        [key.property_list]: {
            alert1: {
                param: {
                    path: id.pathway_list,
                    prop: id.property_list
                }
            },
            alert1: {
                param: {
                    path: id.backup_pathway_list,
                    prop: id.property_list
                }
            },
            alert1: {
                param: {
                    path: id.new_pathway_list,
                    prop: id.property_list
                }
            }
        },
    },
});


/* Hiding/showing elements in DC-Specific forms based on other fields */

// Pathway Selection Form Logic
$(group.affordable_boolean + ', ' + group.type_affordable_housing).hide();

show_hide_type_affordable_housing = function () {
    // type_affordable_housing field appears if "Primary Property Type - Portfolio Manager Calculated" = "Multifamily Housing" AND "Affordable Housing" = TRUE
    if ($(id.property_list).val() == "Multifamily Housing" && $(id.affordable_boolean).prop('checked')) {
        $(group.type_affordable_housing).show();
    } else {
        $(group.type_affordable_housing).hide();
        $(id.type_affordable_housing).val('');
    }
}

// Check if fields need to be shown on form reload
if ($(id.property_list).val() == "Multifamily Housing") {
    $(group.affordable_boolean).show();
} else {
    $(group.affordable_boolean).hide();
    $(id.affordable_boolean).prop('checked', false);
}
show_hide_type_affordable_housing();

// Check if fields need to be marked required on form reload
groups_to_mark = [group.backup_pathway_list, group.attachment];
if ($(id.pathway_list).val() != "Alternative Compliance Pathway") {
    // Show them on ticket reload when there are errors
    $(group.backup_pathway_list).hide();
} else {
    // Mark them as required too, if needed
    groups_to_mark.forEach(e => ! $(e + ' span').length ? $(e + ' label').after('<span style="color:red;">*</span>') : {})
}

$(id.property_list).change(function(){
    //affordable_boolean field appears if the property type is Multifamily Housing
    if ($(id.property_list).val() == "Multifamily Housing") {
        $(group.affordable_boolean).show();
    } else {
        $(group.affordable_boolean).hide();
        $(id.affordable_boolean).prop('checked', false);
    }

    show_hide_type_affordable_housing();

    form_validator.element(id.property_list);

    // Used in Pathway Selection and Pathway Change Application Forms
    //For non-high performing categories: hide the Standard Target Pathway in the Pathway, Backup Pathway, and New Pathway Lists
    lists = [id.pathway_list, id.backup_pathway_list, id.new_pathway_list]
    if ($.inArray($(id.property_list).val(), high_perf) === -1) {
        lists.forEach(function (list) {
            $(list + " option[value='Standard Target Pathway']").remove();
        })
    } else {
        // Add the Standard Target pathway back in for each List
        lists.forEach(function (list) {
            pathway_options = []
            var values = $(list + " option").map(function() {pathway_options.push(this.value);})

            if ($.inArray('Standard Target Pathway', pathway_options) == -1){
                $(list + ' option:eq(1)').after('<option value="Standard Target Pathway">Standard Target Pathway</option>');
            }
        });
    }
});

$(id.affordable_boolean).change(function(){
    show_hide_type_affordable_housing();
});

$(id.pathway_list).change(function(){
    //removes class 'error-okay' so that validator will not ignore changes
    $(id.pathway_list).removeClass("error-okay");
    form_validator.element(id.pathway_list);

    //Alert 1 must be checked when either of two fields changes
    if ($(id.property_list).val() != '')
        form_validator.element(id.property_list);

    // backup_pathway_list "Pathway Selected" = "Alternative Compliance Pathway"
    if ($(id.pathway_list).val() == "Alternative Compliance Pathway") {
        $(group.backup_pathway_list).show();
        // Mark as required
        groups_to_mark.forEach(e => !$(e + ' span').length ? $(e + ' label').after('<span style="color:red;">*</span>') : {})
    } else {
        // Hide Groups and Reset inputs
        $(group.backup_pathway_list).hide();
        $(id.backup_pathway_list).val('');

        // Remove mark as required
        $(groups_to_mark.join(', ')).children('span').remove()

        // Remove error message if a different Pathway was selected before Backup Pathway could be changed
        $(id.backup_pathway_list + '-error').remove();
    }
});

$(id.backup_pathway_list).change(function() {
    //removes class 'error-okay' so that validator will not ignore changes
    $(id.backup_pathway_list).removeClass("error-okay");
    form_validator.element(id.backup_pathway_list);

    //Alert 1 must be checked when either of two fields changes
    if ($(id.backup_pathway_list).val() != '')
        form_validator.element(id.property_list);
});


// Pathway Change Application Form Logic
$(id.new_pathway_list).change(function () {
    //removes class 'error-okay' so that validator will not ignore changes
    $(id.new_pathway_list).removeClass("error-okay");
    form_validator.element(id.new_pathway_list);

    // (Un)Mark Attachment field as required
    if($(id.new_pathway_list).val() == "Alternative Compliance Pathway") {
        $(group.attachment + ' label').after('<span style="color:red;">*</span>');
    } else {
        // Remove mark as required
        $(group.attachment).children('span').remove();
    }
})

/* Hiding/showing elements in Ann Arbor-Specific forms based on other fields */

// Extension/Exemption Request Form Logic
var options = $(id.ext_reason).children();
var values = $.map(options ,function(option) {
    if (option.value != '' && option.value != '-----') {
      return option.value;
    }
});
ext_values = values.slice(0, 4)
exempt_values = values.slice(4, )

$(group.ext_reason).hide();
$(id.ext_or_exempt).change(function () {
  if ($(id.ext_or_exempt).val() != '') {
    $(group.ext_reason).show();
    // Modify Options based on Exempt or Extension
    $(id.ext_reason).empty();   // Remove all choices
    values_to_add = $(id.ext_or_exempt).val() == 'Extension' ? ext_values : exempt_values;
    $(id.ext_reason).append($("<option></option>").attr("value", '').text('---------'));    // Empty first choice
    values_to_add.forEach(val => $(id.ext_reason).append($("<option></option>").attr("value", val).text(val)));
  } else {
    // Reset options
    $(group.ext_reason).hide();
    $(id.ext_reason).val('')
  }
});


/* Hiding/showing elements in dc-staging-Specific forms based on other fields */

// Delay of Compliance Request Form Logic
var QAH_fields = [group.attachment_1, group.type_affordable_housing, group.attachment_3];
if (! $(id.extended_delay_for_QAH).prop('checked')) {
  $(QAH_fields.join(', ')).hide();
  $(id.delay_years).attr({"max" : 3, "min" : 1});
} else {
  $(id.delay_years).attr({"min": 0})
}

$(id.extended_delay_for_QAH).change(function() {
  fields = QAH_fields.join(', ');
  if ($(id.extended_delay_for_QAH).prop('checked')) {
    $(fields).show()
    QAH_fields.forEach(e => $(e + ' label').after('<span style="color:red;">*</span>'))
    $(id.delay_years).attr({"min": 0}).removeAttr('max')
  } else {
    $(fields).hide()
    $(fields).children('span').remove();
    $(id.delay_years).attr({"max" : 3, "min" : 1});
    if ($(id.delay_years).val() > '3') $(id.delay_years).val('3');
  }
});
