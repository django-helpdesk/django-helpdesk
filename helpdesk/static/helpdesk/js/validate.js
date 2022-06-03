//TODO: 'High Performing' is not a type of property -- will need to add an array of 'high performing' types.

/* Variables */

var key = {
    // DC Specific
    affordable_boolean: 'e_is_affordable_housing',
    affordable_list: 'e_type_affordable_housing',
    acp_list: 'e_acp_type',
    property_list: 'e_property_type',
    pathway_list: 'e_pathway',
    backup_pathway_list: 'e_backup_pathway',
    attachment: 'attachment',

    // DC-staging
    extended_delay_for_QAH: 'e_extended_delay_for_QAH',
    delay_years: 'delay_years',
    type_affordable_housing: 'type_affordable_housing',
    attachment_1: 'attachment_1',
    attachment_2: 'attachment_2',
    attachment_3: 'attachment_3',

    // Ann Arbor Specific
    ext_or_exempt: 'e_extension_or_exemption',
    ext_reason: 'e_extension_reason'
};

var id = {};
var group = {};
Object.entries(key).forEach(function (e) {
  id[e[0]] ='#id_' + e[1];
  group[e[0]] = '#id_group_' + e[1];
})

var high_perf = ['Adult Education','Ambulatory Surgical Center','Multifamily Housing','Automobile Dealership','Bank Branch','Bar/Nightclub','Barracks','Courthouse','College/University','Convenience Store with Gas Station','Convenience Store without Gas Station','Financial Office','Data Center','Drinking Water Treatment & Distribution','Enclosed Mall','Office','Fast Food Restaurant','Food Sales','Food Service','Hospital (General Medical & Surgical)','Hotel','Laboratory','Lifestyle Center','Medical Office','Other - Education','Other - Lodging/Residential','Other - Mall','Other - Restaurant/Bar','Other - Specialty Hospital','Outpatient Rehabilitation/Physical Therapy','Pre-school/Daycare','Prison/Incarceration','Residence Hall/Dormitory','Residential Care Facility','Restaurant','Retail Store','Self-Storage Facility','Senior Care Community (also know as Senior Livi Community)','Strip Mall','Supermarket/Grocery Store','Urgent Care/Clinic/Other Outpatient','Veterinary Office','Vocational School','Wastewater Treatment Plant','Wholesale Club/Supercenter']

/* Alerts */

var alertMsg1 = 'This property type is not eligible for the Standard Target Pathway, please select another pathway.';
var alertMsg2 = 'You have selected the Prescriptive Pathway, please note that DOEE will not approve this selection until the building owner has submitted an energy audit. For more information please see this <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS/55/">FAQ</a>.';
var alertMsg3 = 'This property type is not eligible for the Extended Deep Energy Retrofit ACP Option, please select another pathway.'
var alertMsg4 = 'You have selected the Prescriptive Pathway, please note that DOEE will not approve this selection until the building owner has submitted an energy audit. For more information please see this <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS/55/">FAQ</a>'
var alertMsg5 = 'If selecting the ACP, you must select a Backup Pathway and attach an ACP proposal with supporting documentation as specified in <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS_Guidebook/69/">Chapter 4</a> of the <a href="https://dc.beam-portal.org/helpdesk/kb/BEPS_Guidebook/">BEPS Guidebook</a>.'

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

/*  This field appears
    if "ACP Option" =  "Extended Deep Energy Retrofit"
    AND ("Affordable Housing/Rent Controlled?" = FALSE
    OR ("Primary Property Type - Portfolio Manager Calculated" != "College/University" OR "Hospital").
    If this alert text appears the user should not be able to submit the form, until they select another pathway */
jQuery.validator.addMethod('alert3', function (value, element, param) {
    return this.optional(element) || !( value == "Extended Deep Energy Retrofit" && ( !$(param.affordable).prop('checked') || ($(param.prop).val() != "College/University" || $(param.prop).val() != "Hospital")) );
}, alertMsg3);

/*   if "ACP Option" =  "Extended Deep Energy Retrofit"
    AND ("Affordable Housing/Rent Controlled?" = TRUE
    OR ("Primary Property Type - Portfolio Manager Calculated" = "College/University" OR "Hospital").
    If this alert text appears the user should not be able to submit the form, until they select another pathway */
jQuery.validator.addMethod('alert4', function (value, element, param) {
    return this.optional(element) || !( value == "Extended Deep Energy Retrofit" && ( $(param.affordable).prop('checked') || ($(param.prop).val() == "College/University" || $(param.prop).val() == "Hospital")) );
}, alertMsg4);

jQuery.validator.addMethod('alert5', function (value, element) {
    var ok =  this.optional(element) || value != 'Alternative Compliance Pathway';
    if(!ok) $(element).addClass("error-okay");
    else $(element).removeClass("error-okay");
    return ok;
}, alertMsg5);


/* Validations */

var form_validator = $('#ticket_submission_form').validate({
    ignore: '.error-okay',
    rules: {
        [key.pathway_list]: {
            alert2: true,
            alert5: true
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
            }
        },
        [key.acp_list]: {
            alert3: {
                param: {
                    affordable: id.affordable_boolean,
                    prop: id.property_list
                }
            },
            alert4: {
                param: {
                    affordable: id.affordable_boolean,
                    prop: id.property_list
                }
            },
        }
    },
});


/* Hiding/showing elements in DC-Specific forms based on other fields */
$(group.affordable_boolean).hide();
$(group.affordable_list).hide();
if ($(id.pathway_list).val() != "Alternative Compliance Pathway") {
    // Show them on ticket reload when there are errors
    $(group.acp_list).hide();
    $(group.backup_pathway_list).hide();
}

$(id.property_list).change(function(){
    //Alert 3 must be checked when either of two fields changes
     if ($(id.acp_list).val() != '' && $(id.affordable_boolean).prop('checked'))
        form_validator.element(id.acp_list);

    //affordable_boolean field appears if the property type is Multifamily Housing
    if($(id.property_list).val() == "Multifamily Housing") {
        $(group.affordable_boolean).show();
    } else {
        $(group.affordable_boolean).hide();
        $(id.affordable_boolean).prop('checked', false);
    }

    //affordable_list field appears if "Primary Property Type - Portfolio Manager Calculated" = "Multifamily Housing" AND "Affordable Housing" = TRUE
    if($(id.property_list).val() == "Multifamily Housing" && $(id.affordable_boolean).prop('checked')) {
        $(group.affordable_list).show();
    } else {
        $(group.affordable_list).hide();
        $(id.affordable_list).val('');
    }

   //For non-high performing categories: hide the Standard Target Pathway
    if ($.inArray($(id.property_list).val(), high_perf) == -1) {
        $(id.pathway_list + " option[value='Standard Target Pathway']").remove();
    } else {
        pathway_options = []
        var values = $(id.pathway_list + " option").map(function() {pathway_options.push(this.value);})
        if ($.inArray('Standard Target Pathway', pathway_options) == -1){
            $(id.pathway_list).append('<option>Standard Target Pathway</option>');
        }
    }

});

$(id.affordable_boolean).change(function(){
    //Alert 4 must be checked when either of two fields changes
    if ($(id.acp_list).val() != '' && $(id.property_list).val() != '')
        form_validator.element(id.acp_list);

    //affordable_list field appears if "Primary Property Type - Portfolio Manager Calculated" = "Multifamily Housing" AND "Affordable Housing" = TRUE
    if($(id.property_list).val() == "Multifamily Housing" && $(id.affordable_boolean).prop('checked')) {
        $(group.affordable_list).show();
    } else {
        $(group.affordable_list).hide();
        $(id.affordable_list).val('');
    }
});

$(id.pathway_list).change(function(){
    //removes class 'error-okay' so that validator will not ignore changes
    $(id.pathway_list).removeClass("error-okay");
    form_validator.element(id.pathway_list);

    //Alert 1 must be checked when either of two fields changes
    if ($(id.property_list).val() != '')
        form_validator.element(id.property_list);

    // backup_pathway_list and acp_list fields appears if "Pathway Selected" = "Alternative Compliance Pathway"
    if($(id.pathway_list).val() == "Alternative Compliance Pathway") {
        $(group.acp_list).show();
        $(group.backup_pathway_list).show();
        // Mark as required
        $(group.backup_pathway_list+ ' label').after('<span style="color:red;">*</span>');
        $(group.acp_list + ' label').after('<span style="color:red;">*</span>');
        $(group.attachment + ' label').after('<span style="color:red;">*</span>');
    } else {
        // Hide and Reset fields
        $(group.acp_list).hide();
        $(id.acp_list).val('');
        $(group.backup_pathway_list).hide();
        $(id.backup_pathway_list).val('');
        // Remove mark as required
        $(group.acp_list).children('span').remove();
        $(group.backup_pathway_list).children('span').remove();
        $(group.attachment).children('span').remove();
    }
});

$(id.backup_pathway_list).change(function() {
    //removes class 'error-okay' so that validator will not ignore changes
    $(id.backup_pathway_list).removeClass("error-okay");
    form_validator.element(id.backup_pathway_list);

    //Alert 1 must be checked when either of two fields changes
    if ($(id.backup_pathway_list).val() != '')
        form_validator.element(id.backup_pathway_list);
});



/* Hiding/showing elements in Ann Arbor-Specific forms based on other fields */
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
    $.each(values_to_add, function(index, val) {
      $(id.ext_reason).append($("<option></option>").attr("value", val).text(val));   // add in specific choices
    });
  } else {
    // Reset options
    $(group.ext_reason).hide();
    $(id.ext_reason).val('')
  }


});


/* Hiding/showing elements in dc-staging-Specific forms based on other fields */
var QAH_fields = [group.attachment_1, group.type_affordable_housing, group.attachment_3].join(', ');
if (! $(id.extended_delay_for_QAH).prop('checked')) {
  $(QAH_fields).each(function(ind, e) {
    // Only hide if field is not checked, otherwise show in case of Page reload or on error
    $(e).hide();
  })
  $(id.delay_years).attr({"max" : 3, "min" : 1});
} else {
  $(id.delay_years).attr({"min": 0})
}

$(id.extended_delay_for_QAH).change(function() {
  if ($(id.extended_delay_for_QAH).prop('checked')) {
    $(QAH_fields).each(function(ind, e) {
      $(e).show();
      // Mark as Required
      $('#' + e.id + ' label').after('<span style="color:red;">*</span>');
      $(id.delay_years).attr({"min": 0}).removeAttr('max')
    })
  } else {
    $(QAH_fields).each(function(ind, e) {
      $(e).hide();
      $(e).children('span').remove();
      $(id.delay_years).attr({"max" : 3, "min" : 1});
      if ($(id.delay_years).val() > '3') {
        $(id.delay_years).val('3');
      }
    })
  }
})
