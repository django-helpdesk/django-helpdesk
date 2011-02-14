/**
 * Copyright (c) 2009 - 2010 Chris Leonello
 * jqPlot is currently available for use in all personal or commercial projects 
 * under both the MIT (http://www.opensource.org/licenses/mit-license.php) and GPL 
 * version 2.0 (http://www.gnu.org/licenses/gpl-2.0.html) licenses. This means that you can 
 * choose the license that best suits your project and use it accordingly. 
 *
 * Although not required, the author would appreciate an email letting him 
 * know of any substantial use of jqPlot.  You can reach the author at: 
 * chris at jqplot  or see http://www.jqplot.com/info.php .
 *
 * If you are feeling kind and generous, consider supporting the project by
 * making a donation at: http://www.jqplot.com/donate.php .
 *
 * jqPlot includes date instance methods and printf/sprintf functions by other authors:
 *
 * Date instance methods contained in jqplot.dateMethods.js:
 *
 *     author Ken Snyder (ken d snyder at gmail dot com)
 *     date 2008-09-10
 *     version 2.0.2 (http://kendsnyder.com/sandbox/date/)     
 *     license Creative Commons Attribution License 3.0 (http://creativecommons.org/licenses/by/3.0/)
 *
 * JavaScript printf/sprintf functions contained in jqplot.sprintf.js:
 *
 *     version 2007.04.27
 *     author Ash Searle
 *     http://hexmen.com/blog/2007/03/printf-sprintf/
 *     http://hexmen.com/js/sprintf.js
 *     The author (Ash Searle) has placed this code in the public domain:
 *     "This code is unrestricted: you are free to use it however you like."
 * 
 */
(function(a){a.jqplot.EnhancedLegendRenderer=function(){a.jqplot.TableLegendRenderer.call(this)};a.jqplot.EnhancedLegendRenderer.prototype=new a.jqplot.TableLegendRenderer();a.jqplot.EnhancedLegendRenderer.prototype.constructor=a.jqplot.EnhancedLegendRenderer;a.jqplot.EnhancedLegendRenderer.prototype.init=function(b){this.numberRows=null;this.numberColumns=null;this.seriesToggle="normal";this.disableIEFading=true;a.extend(true,this,b);if(this.seriesToggle){a.jqplot.postDrawHooks.push(postDraw)}};a.jqplot.EnhancedLegendRenderer.prototype.draw=function(){var t=this;if(this.show){var m=this._series;var u="position:absolute;";u+=(this.background)?"background:"+this.background+";":"";u+=(this.border)?"border:"+this.border+";":"";u+=(this.fontSize)?"font-size:"+this.fontSize+";":"";u+=(this.fontFamily)?"font-family:"+this.fontFamily+";":"";u+=(this.textColor)?"color:"+this.textColor+";":"";u+=(this.marginTop!=null)?"margin-top:"+this.marginTop+";":"";u+=(this.marginBottom!=null)?"margin-bottom:"+this.marginBottom+";":"";u+=(this.marginLeft!=null)?"margin-left:"+this.marginLeft+";":"";u+=(this.marginRight!=null)?"margin-right:"+this.marginRight+";":"";this._elem=a('<table class="jqplot-table-legend" style="'+u+'"></table>');if(this.seriesToggle){this._elem.css("z-index","3")}var d=false,o=false,q,l;if(this.numberRows){q=this.numberRows;if(!this.numberColumns){l=Math.ceil(m.length/q)}else{l=this.numberColumns}}else{if(this.numberColumns){l=this.numberColumns;q=Math.ceil(m.length/this.numberColumns)}else{q=m.length;l=1}}var n,k,p,e,c,h,g;var r=0;for(n=m.length-1;n>=0;n--){if(m[n]._stack||m[n].renderer.constructor==a.jqplot.BezierCurveRenderer){o=true}}for(n=0;n<q;n++){if(o){p=a('<tr class="jqplot-table-legend"></tr>').prependTo(this._elem)}else{p=a('<tr class="jqplot-table-legend"></tr>').appendTo(this._elem)}for(k=0;k<l;k++){if(r<m.length&&m[r].show&&m[r].showLabel){s=m[r];h=this.labels[r]||s.label.toString();if(h){var f=s.color;if(!o){if(n>0){d=true}else{d=false}}else{if(n==q-1){d=false}else{d=true}}g=(d)?this.rowSpacing:"0";e=a('<td class="jqplot-table-legend" style="text-align:center;padding-top:'+g+';"><div><div class="jqplot-table-legend-swatch" style="background-color:'+f+";border-color:"+f+';"></div></div></td>');c=a('<td class="jqplot-table-legend" style="padding-top:'+g+';"></td>');if(this.escapeHtml){c.text(h)}else{c.html(h)}if(o){if(this.showLabels){c.prependTo(p)}if(this.showSwatches){e.prependTo(p)}}else{if(this.showSwatches){e.appendTo(p)}if(this.showLabels){c.appendTo(p)}}if(this.seriesToggle){var b;if(typeof(this.seriesToggle)=="string"||typeof(this.seriesToggle)=="number"){if(!a.browser.msie||!this.disableIEFading){b=this.seriesToggle}}if(this.showSwatches){e.bind("click",{series:s,speed:b},s.toggleDisplay);e.addClass("jqplot-seriesToggle")}if(this.showLabels){c.bind("click",{series:s,speed:b},s.toggleDisplay);c.addClass("jqplot-seriesToggle")}}d=true}}r++}}}return this._elem};postDraw=function(){if(this.legend.renderer.constructor==a.jqplot.EnhancedLegendRenderer&&this.legend.seriesToggle){var b=this.legend._elem.detach();this.eventCanvas._elem.after(b)}}})(jQuery);